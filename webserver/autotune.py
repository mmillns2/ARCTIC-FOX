import threading
import time
import math


class AutotuneState:
    IDLE     = "idle"
    SETTLING = "settling"
    RELAY    = "relay"
    DONE     = "done"
    FAILED   = "failed"


class Autotune:

    def __init__(self, relay_high, relay_low, setpoint, pid_fn,
                 noise_band=0.02, min_cycles=6,
                 max_time=1800, min_dwell_time=60.0):
        """
        relay_high:     output when heating during relay experiment
        relay_low:      output when above setpoint during relay experiment
        setpoint:       final target temperature
        pid_fn:         the PID object, called during settling to actively
                        drive the temperature toward setpoint
        noise_band:     K, hysteresis around setpoint for relay switching
                        and settling detection. set to a few times your
                        sensor noise floor.
        min_cycles:     number of complete oscillations before computing gains
        max_time:       seconds before relay gives up and marks as failed
        min_dwell_time: seconds temp must stay within noise_band before
                        relay starts
        """
        self.relay_high     = relay_high
        self.relay_low      = relay_low
        self.setpoint       = setpoint
        self._pid_fn        = pid_fn
        self.noise_band     = noise_band
        self.min_cycles     = min_cycles
        self.max_time       = max_time
        self.min_dwell_time = min_dwell_time

        self.state          = AutotuneState.SETTLING
        self._lock          = threading.Lock()

        self._output_high   = True
        self._peaks         = []
        self._valleys       = []
        self._last_temp     = None
        self._looking_for   = "peak"
        self._start_time    = None
        self._dwell_timer   = 0.0
        self._crossed_above = False
        self._crossed_below = False

        self.kp = None
        self.ki = None
        self.kd = None

    def start(self, current_temp):
        with self._lock:
            self._last_temp   = current_temp
            self._dwell_timer = 0.0

    def update(self, temp, dt):
        """
        Call every sample tick after the ramp has finished.
        dt is the time in seconds since the last call.
        Returns (output, done) where output is the value to write
        to hardware and done is True when the experiment has ended.
        """
        with self._lock:
            if self.state == AutotuneState.SETTLING:
                return self._settling_tick(temp, dt)
            elif self.state == AutotuneState.RELAY:
                return self._relay_tick(temp)
            else:
                return None, True

    def _settling_tick(self, temp, dt):
        """
        Runs the PID during settling so the temperature is actively driven
        toward setpoint rather than sitting with zero output. The dwell timer
        only starts counting once temp is within noise_band and resets if
        it drifts out again.
        """
        out = self._pid_fn(temp)

        if abs(temp - self.setpoint) < self.noise_band:
            self._dwell_timer += dt
        #    print(f"[Autotune] settling: {self._dwell_timer:.0f}s "
        #          f"/ {self.min_dwell_time:.0f}s  temp={temp:.4f}")
        else:
            self._dwell_timer = 0.0

        if self._dwell_timer >= self.min_dwell_time:
        #    print(f"[Autotune] settled, starting relay experiment")
            self.state          = AutotuneState.RELAY
            self._start_time    = time.time()
            self._output_high   = True
            self._crossed_above = False
            self._crossed_below = False

        return out, False

    def _relay_tick(self, temp):
        """
        Switches output between relay_high and relay_low based on which
        side of setpoint the temperature is on. Records peaks and valleys
        only when the temperature has genuinely crossed setpoint in the
        corresponding direction, filtering out noise-driven detections.
        """
        now = time.time()

        if now - self._start_time > self.max_time:
        #    print(f"[Autotune] timed out after {self.max_time}s")
            self.state = AutotuneState.FAILED
            return None, True

        # switch relay when temp crosses setpoint with hysteresis.
        # noise_band prevents chattering when temp is near setpoint.
        if temp > self.setpoint + self.noise_band:
            self._output_high   = False
            self._crossed_above = True
        elif temp < self.setpoint - self.noise_band:
            self._output_high   = True
            self._crossed_below = True

        # detect peaks and valleys only if temperature has genuinely
        # crossed setpoint in the corresponding direction
        if self._last_temp is not None:
            if self._looking_for == "peak" and temp < self._last_temp:
                if self._crossed_above:
                    self._peaks.append((now, self._last_temp))
                    self._looking_for   = "valley"
                    self._crossed_above = False
        #            print(f"[Autotune] peak at {self._last_temp:.4f}  "
        #                  f"cycles={min(len(self._peaks), len(self._valleys))}")

            elif self._looking_for == "valley" and temp > self._last_temp:
                if self._crossed_below:
                    self._valleys.append((now, self._last_temp))
                    self._looking_for   = "peak"
                    self._crossed_below = False
        #            print(f"[Autotune] valley at {self._last_temp:.4f}  "
        #                  f"cycles={min(len(self._peaks), len(self._valleys))}")

        self._last_temp = temp

        n_cycles = min(len(self._peaks), len(self._valleys))
        if n_cycles >= self.min_cycles:
            success    = self._compute_gains()
            self.state = AutotuneState.DONE if success else AutotuneState.FAILED
            return None, True

        output = self.relay_high if self._output_high else self.relay_low
        #print(f"[Autotune] temp={temp:.4f}  output={output:.3f}  "
        #      f"peaks={len(self._peaks)}  valleys={len(self._valleys)}")
        return output, False

    def _compute_gains(self):
        """
        Computes Kp, Ki, Kd from the measured oscillation.

        Tu is the average peak-to-peak period. a is the average half-swing
        amplitude across matched peak/valley pairs. d is the half-swing of
        the relay output. Ku is the ultimate gain from describing function
        analysis: Ku = 4d / (pi * a). Gains use the some-overshoot
        Ziegler-Nichols variant which is more conservative than standard ZN.
        """
        peak_times = [t for t, _ in self._peaks]
        if len(peak_times) < 2:
            print("[Autotune] not enough peaks to compute period")
            return False

        periods = [peak_times[i+1] - peak_times[i]
                   for i in range(len(peak_times) - 1)]
        Tu = sum(periods) / len(periods)

        peak_vals   = [v for _, v in self._peaks]
        valley_vals = [v for _, v in self._valleys]
        n           = min(len(peak_vals), len(valley_vals))
        amplitudes  = [(peak_vals[i] - valley_vals[i]) / 2.0 for i in range(n)]
        a           = sum(amplitudes) / len(amplitudes)

        if a <= 0 or Tu <= 0:
            print("[Autotune] invalid amplitude or period")
            return False

        d  = (self.relay_high - self.relay_low) / 2.0
        Ku = (4.0 * d) / (math.pi * a)

        self.kp = 0.33 * Ku
        self.ki = 0.66 * Ku / Tu
        self.kd = 0.11 * Ku * Tu

        #print(f"[Autotune] Tu={Tu:.1f}s  a={a:.4f}  Ku={Ku:.4f}")
        #print(f"[Autotune] Kp={self.kp:.4f}  Ki={self.ki:.4f}  Kd={self.kd:.4f}")
        return True

    def status(self):
        with self._lock:
            return {
                "state":  self.state,
                "cycles": min(len(self._peaks), len(self._valleys)),
                "kp":     self.kp,
                "ki":     self.ki,
                "kd":     self.kd,
            }

    def gains(self):
        with self._lock:
            return self.kp, self.ki, self.kd
