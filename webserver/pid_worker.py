import threading
import time
import math
from simple_pid import PID
from autotune import Autotune, AutotuneState


class PIDWorker(threading.Thread):

    def __init__(self, name, hwio, read_temp_fn, write_output_fn,
                 kp, ki, kd,
                 out_min, out_max,
                 ramp_rate=10,
                 relay_high_fraction=1.0,
                 relay_low=0.0,
                 noise_band=0.02,
                 min_dwell_time=0.0,
                 min_cycles=3,
                 max_time=1800,
                 gain_cache_tolerance=0.5,
                 sample_time=3.0,
                 autotune_enabled=True,
                 use_threshold=False,
                 threshold=None,
                 recapture=None,
                 hold_output=0.0,
                 stage1_setpoint=None,
                 stage1_duration=600.0):
        """
        kp, ki, kd:             conservative gains for ramp tracking before
                                autotune runs. kd=0 is recommended.
        out_min, out_max:       hardware output limits
        ramp_rate:              K/min, how fast the setpoint climbs.
                                the ramp follows an exponential approach so
                                this is the initial rate at the start of the
                                ramp, tapering off naturally near setpoint.
        relay_high_fraction:    fraction of out_max to apply when heating
                                during relay. start at 0.3.
        relay_low:              output when above setpoint during relay.
                                0 works unless base cooling power is significant.
        noise_band:             K, hysteresis for relay switching and settling.
                                set to a few times your sensor noise floor.
        min_dwell_time:         seconds temp must stay within noise_band before
                                relay starts.
        min_cycles:             complete oscillations before computing gains.
        max_time:               seconds before relay gives up.
        gain_cache_tolerance:   K, how close a previous setpoint must be to
                                reuse cached gains.
        sample_time:            seconds between ticks.
        """
        super().__init__(daemon=True)
        self.name                 = name
        self.hwio                 = hwio
        self.read_temp_fn         = read_temp_fn
        self.write_output_fn      = write_output_fn
        self.out_min              = out_min

        self.out_max              = out_max
        self.relay_high_fraction  = relay_high_fraction
        self.relay_low            = relay_low
        self.noise_band           = noise_band
        self.min_dwell_time       = min_dwell_time
        self.min_cycles           = min_cycles
        self.max_time             = max_time
        self.gain_cache_tolerance = gain_cache_tolerance
        self.sample_time          = sample_time
        self.autotune_enabled = bool(autotune_enabled)
        self.use_threshold    = bool(use_threshold)
        self.threshold        = threshold
        self.recapture        = recapture
        self.hold_output      = float(hold_output)
        self.stage1_setpoint = stage1_setpoint
        self.stage1_duration = float(stage1_duration)
        self._stage          = None
        self._stage1_start_temp = None
        self._stage1_start_time = None

        self._gated           = False
        self._hold_estimate   = None

        if self.use_threshold:
            if threshold is None or recapture is None:
                raise ValueError(f"[{name}] use_threshold needs threshold and recapture")
            if recapture >= threshold:
                raise ValueError(f"[{name}] recapture must be below threshold")

        self._last_ramp_output    = None
        self._ramping_done        = False

        # convert ramp_rate from K/min to a time constant tau in seconds.
        # the exponential approach moves at ramp_rate K/min initially and
        # tapers off as it approaches the setpoint. tau is chosen so the
        # initial slope matches the requested ramp_rate.
        self._ramp_rate_Ks = ramp_rate / 60.0

        self.pid = PID(kp, ki, kd,
                       output_limits=(self.out_min, self.out_max),
                       proportional_on_measurement=False)

        self._final_setpoint  = None
        self._ramp_start_temp = None
        self._ramp_start_time = None
        self._autotuner       = None
        self._gains_measured  = not self.autotune_enabled
        self._gain_cache      = {}
        self._last_tick_time  = None

        self._enabled         = threading.Event()
        self._stop_event      = threading.Event()
        self._lock            = threading.Lock()

    def set_setpoint(self, sp):
        with self._lock:
            self._final_setpoint  = sp
            self._ramp_start_temp = None
            self._ramp_start_time = None
            self._autotuner       = None
            self._ramping_done    = False

            if self._gated:
                self.pid.set_auto_mode(True, last_output=self.hold_output)
            self._gated           = False

            # arm the slow intermediate leg (3-pumps only)
            if self.stage1_setpoint is not None and sp > self.stage1_setpoint:
                self._stage = 1
                self._stage1_start_temp = None      # set on first tick
                self._stage1_start_time = None
                print(f"[PIDWorker:{self.name}] stage 1: slow ramp to "
                      f"{self.stage1_setpoint} K over {self.stage1_duration:.0f}s")
            else:
                self._stage = None

            if not self.autotune_enabled:        
                self._gains_measured = True
                return

            cached = self._find_cached_gains(sp)
            if cached:
                self.pid.tunings     = cached
                self._gains_measured = True
                print(f"[PIDWorker:{self.name}] using cached gains for {sp}")
            else:
                self._gains_measured = False

    def _find_cached_gains(self, sp):
        for cached_sp, gains in self._gain_cache.items():
            if abs(cached_sp - sp) < self.gain_cache_tolerance:
                return gains
        return None

    def enable(self):
        self._enabled.set()
        print(f"[PIDWorker:{self.name}] enabled")

    def disable(self):
        self._enabled.clear()
        self._gated = False
        self.write_output_fn(0.0)
        print(f"[PIDWorker:{self.name}] disabled")

    def shutdown(self):
        self._stop_event.set()
        self.join()

    def status(self):
        with self._lock:
            autotune = self._autotuner.status() if self._autotuner else {
                "state": AutotuneState.IDLE
            }
            return {
                "final_setpoint": self._final_setpoint,
                "gains_measured": self._gains_measured,
                "autotune":       autotune,
                "gated":          self._gated,             
                "hold_estimate":  self._hold_estimate,     
            }

    def run(self):
        print(f"[PIDWorker:{self.name}] thread started")
        while not self._stop_event.is_set():
            if self._enabled.is_set():
                try:
                    self._tick()
                except Exception as e:
                    print(f"[PIDWorker:{self.name}] ERROR: {e}")
            time.sleep(self.sample_time)

    def _tick(self):
        now  = time.time()
        dt   = now - self._last_tick_time if self._last_tick_time else self.sample_time
        self._last_tick_time = now

        temp = self.read_temp_fn()
        if temp is None:
            return

        with self._lock:
            if self._final_setpoint is None:
                return

            # two-stage pump heating: slow leg to intermediate sp first
            if self._stage == 1:
                self._stage1_tick(temp, now)
                return

            # initialise ramp tracking on the first tick after set_setpoint
            if self._ramp_start_temp is None:
                self._ramp_start_temp = temp
                self._ramp_start_time = now

            # exponential approach: ramped_sp starts at current temp and
            # approaches final_setpoint with a time constant tau.
            # tau is chosen so the initial slope matches ramp_rate_Ks:
            #   d/dt [final_sp - (final_sp - start) * exp(-t/tau)] at t=0
            #   = (final_sp - start) / tau = ramp_rate_Ks
            #   so tau = (final_sp - start) / ramp_rate_Ks
            span = self._final_setpoint - self._ramp_start_temp
            if abs(span) > 0 and self._ramp_rate_Ks > 0:
                tau = abs(span) / self._ramp_rate_Ks
            else:
                tau = 1.0

            elapsed       = now - self._ramp_start_time
            ramped_sp     = (self._final_setpoint -
                             span * math.exp(-elapsed / tau))

            if not self._ramping_done:
                self._ramping_done  = (
                    abs(ramped_sp - self._final_setpoint) < 0.5 and 
                    abs(temp - self._final_setpoint) < 0.05
                ) or self.use_threshold

            if not self._ramping_done:
                self._ramp_tick(temp, ramped_sp, dt)
            elif self._autotuner is not None:
                self._autotune_tick(temp, dt)
            else:
                self._pid_tick(temp)

    def _stage1_tick(self, temp, now):
        # initialise on first tick
        if self._stage1_start_temp is None:
            self._stage1_start_temp = temp
            self._stage1_start_time = now

        elapsed = now - self._stage1_start_time
        frac    = min(elapsed / self.stage1_duration, 1.0)

        # linear climb from start temp to stage1_setpoint
        span      = self.stage1_setpoint - self._stage1_start_temp
        target_sp = self._stage1_start_temp + span * frac

        self.pid.setpoint = target_sp
        out = self.pid(temp)
        self.write_output_fn(out)

        print(f"[PIDWorker:{self.name}] stage1: "
              f"temp={temp:.2f}  target={target_sp:.2f}  "
              f"final={self.stage1_setpoint:.2f}  "
              f"t={elapsed:.0f}/{self.stage1_duration:.0f}s  out={out:.3f}")

        # done: time elapsed AND temperature actually arrived
        if frac >= 1.0 and temp >= self.stage1_setpoint - 0.5:
            print(f"[PIDWorker:{self.name}] stage 1 complete at {temp:.2f} K, "
                  f"handing off to stage 2 (final={self._final_setpoint})")
            self._stage           = None
            self._ramp_start_temp = None      # let normal ramp re-init to final
            self._ramp_start_time = None

    def _ramp_tick(self, temp, ramped_sp, dt):
        """
        PID tracks the exponentially increasing ramped setpoint.
        Output is cut if temperature overshoots the ramped setpoint
        to avoid building momentum ahead of the ramp.
        """
        if temp > ramped_sp * 1.01:
            self.write_output_fn(0.0)
            return

        self.pid.setpoint = ramped_sp
        out = self.pid(temp)
        self._last_ramp_output = out
        self.write_output_fn(out)
        if self.name == 'Still [K]':
            print(f"[PIDWorker:{self.name}] ramping: "
                  f"temp={temp:.3f}  "
                  f"ramped_sp={ramped_sp:.3f}  "
                  f"final_sp={self._final_setpoint:.3f}  "
                  f"out={out:.3f}")

    def _autotune_tick(self, temp, dt):
        output, done = self._autotuner.update(temp, dt)

        if output is not None:
            self.write_output_fn(output)

        if not done:
            return

        if self._autotuner.state == AutotuneState.DONE:
            kp, ki, kd = self._autotuner.gains()
            self._gain_cache[self._final_setpoint] = (kp, ki, kd)
            self.pid.tunings  = (kp, ki, kd)
            self.pid.setpoint = self._final_setpoint
            # seed the PID integral from the relay's last output so
            # the handoff is smooth with no step change in output
            self.pid.set_auto_mode(True, last_output=output or 0.0)
            print(f"[PIDWorker:{self.name}] autotune done, handing off to PID")
        else:
            print(f"[PIDWorker:{self.name}] autotune failed, using current gains")

        self._gains_measured = True
        self._autotuner      = None

    def _pid_tick(self, temp):
        self.pid.setpoint = self._final_setpoint

        if self.use_threshold:
            # gate transitions 
            if not self._gated and temp > self.threshold:
                self.pid.auto_mode = False              # freeze integrator
                self._gated = True
                print(f"[PIDWorker:{self.name}] gated: "
                      f"{temp:.4f} K > {self.threshold:.4f} K")

            elif self._gated and temp < self.recapture:
                seed = (self._hold_estimate if self._hold_estimate is not None
                        else self.hold_output)
                self.pid.set_auto_mode(True, last_output=seed)   # bumpless
                self._gated = False
                print(f"[PIDWorker:{self.name}] recaptured at "
                      f"{temp:.4f} K, seed={seed:.4g}")

            # act on current state 
            if self._gated:
                self.write_output_fn(0.0)
                return

        # above setpoint: cut output and wait for passive cooling
        if not self.use_threshold and temp > self._final_setpoint * 1.01:
            self.write_output_fn(0.0)
            return

        # ramp complete, gains not yet measured: start autotune.
        # reset the PID first so integral windup from the ramp approach
        # does not carry over and push the temperature past setpoint.
        if not self._gains_measured and self._autotuner is None:
            print(f"[PIDWorker:{self.name}] ramp complete, starting autotune")
            self.pid.reset()
            self._autotuner = Autotune(
                relay_high    =self._last_ramp_output*self.relay_high_fraction,
                relay_low     =self.relay_low,
                setpoint      =self._final_setpoint,
                pid_fn        =self.pid,
                noise_band    =self.noise_band,
                min_cycles    =self.min_cycles,
                max_time      =self.max_time,
                min_dwell_time=self.min_dwell_time,
            )
            self._autotuner.start(temp)
            return

        out = self.pid(temp)
        self.write_output_fn(out)

        if self.name == 'Still [K]':
            print(f"[PIDWorker:{self.name}] pid tick: "
                  f"temp={temp:.3f}  "
                  f"final_sp={self._final_setpoint:.3f}  "
                  f"out={out:.3f}")


