# algorithm.py
import time
from threading import Thread, Event
from dataclasses import dataclass
from typing import Optional

from controller_server import DeviceControllerServer

# ---------------- Side config ----------------
@dataclass
class SideConfig:
    t_switches_off: int = 600
    t_heaters_on: int = 1200
    t_switch_on: int = 900
    t_between_sides: int = 2700
    heater_3puheat: float = 50.0
    heater_4puheat: float = 50.0
    switch_3swheat: float = 7.0
    switch_4swheat: float = 7.0

# ---------------- Pre-cooling config ----------------
@dataclass
class PreCoolingConfig:
    enabled: bool = False
    value: float = 0.0

# ---------------- Algorithm config ----------------
@dataclass
class AlgorithmConfig:
    A: SideConfig = SideConfig()
    B: SideConfig = SideConfig()

    initial_precool: PreCoolingConfig = PreCoolingConfig(
        enabled=False,
        value=50.0
    )

    pre_cycle_cool: PreCoolingConfig = PreCoolingConfig(
        enabled=False,
        value=7.0
    )

# ---------------- Cycle thread ----------------
class Cycle(Thread):
    def __init__(
        self,
        controller: DeviceControllerServer,
        config: AlgorithmConfig,
        last_values: dict,
        last_states: dict
    ):
        super().__init__(daemon=True)
        self.controller = controller
        self.config = config
        self.last_values = last_values
        self.last_states = last_states
        self.stop_event = Event()

        self.state = "Idle"
        self.step_start: Optional[float] = None
        self.step_total: int = 1
        self.current_side: Optional[str] = None

    def stop(self):
        self.stop_event.set()

    # ---------------- Step handling ----------------
    def set_step(self, state: str, duration: Optional[int]):
        self.state = state
        self.step_start = time.time()
        self.step_total = duration if duration is not None else 1

    # ---------------- Interruptible sleep ----------------
    def sleep(self, seconds: int) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            if self.stop_event.is_set():
                return False
            time.sleep(0.5)
        return True

    # ---------------- Send command with retries ----------------
    def send_and_update(self, device, channel, cmd_func, value=None, retries=3):
        for attempt in range(1, retries + 1):
            try:
                if value is not None:
                    cmd_func(device, channel, value)
                    self.last_values[(device, channel)] = value
                    self.last_states[(device, channel)] = "on"
                else:
                    cmd_func(device, channel)
                    self.last_values[(device, channel)] = None
                    self.last_states[(device, channel)] = "off"
                return True
            except Exception as e:
                print(
                    f"[Cycle] Attempt {attempt} failed "
                    f"for {device}:{channel} -> {e}"
                )
                time.sleep(0.2)
        return False

    # ---------------- Run one side ----------------
    def run_side(self, side_name: str, c: SideConfig) -> bool:
        self.current_side = side_name

        # Switches off
        self.set_step(f"{side_name}: switches off", c.t_switches_off)
        if not self.send_and_update(
            side_name, "4swheat",
            self.controller.turn_off_switch
        ):
            return False
        if not self.send_and_update(
            side_name, "3swheat",
            self.controller.turn_off_switch
        ):
            return False
        if not self.sleep(c.t_switches_off):
            return False

        # Heaters on
        self.set_step(f"{side_name}: heaters on", c.t_heaters_on)
        if not self.send_and_update(
            side_name, "4puheat",
            self.controller.set_heater_temperature,
            c.heater_4puheat
        ):
            return False
        if not self.send_and_update(
            side_name, "3puheat",
            self.controller.set_heater_temperature,
            c.heater_3puheat
        ):
            return False
        if not self.sleep(c.t_heaters_on):
            return False

        # 4puheat off, 4swheat on
        self.set_step(
            f"{side_name}: 4puheat off, 4swheat on",
            c.t_switch_on
        )
        if not self.send_and_update(
            side_name, "4puheat",
            self.controller.turn_off_heater
        ):
            return False
        if not self.send_and_update(
            side_name, "4swheat",
            self.controller.set_switch_voltage,
            c.switch_4swheat
        ):
            return False
        if not self.sleep(c.t_switch_on):
            return False

        # 3puheat off, 3swheat on (no timed wait)
        self.set_step(
            f"{side_name}: 3puheat off, 3swheat on",
            None
        )
        if not self.send_and_update(
            side_name, "3puheat",
            self.controller.turn_off_heater
        ):
            return False
        if not self.send_and_update(
            side_name, "3swheat",
            self.controller.set_switch_voltage,
            c.switch_3swheat
        ):
            return False

        return True

    # ---------------- Main loop ----------------
    def run(self):
        print("[Cycle] Algorithm started")
        try:
            while not self.stop_event.is_set():
                if not self.run_side("CTC100A", self.config.A):
                    break

                self.set_step(
                    "Sleeping between sides",
                    self.config.A.t_between_sides
                )
                if not self.sleep(self.config.A.t_between_sides):
                    break

                if not self.run_side("CTC100B", self.config.B):
                    break

                self.set_step(
                    "Sleeping between sides",
                    self.config.B.t_between_sides
                )
                if not self.sleep(self.config.B.t_between_sides):
                    break
        finally:
            self.set_step("Stopped", None)
            self.current_side = None
            print("[Cycle] Algorithm stopped")

    # ---------------- Status API ----------------
    def get_status(self):
        elapsed = 0.0
        if self.step_start is not None:
            elapsed = time.time() - self.step_start

        return {
            "running": self.is_alive() and not self.stop_event.is_set(),
            "state": self.state,
            "side": self.current_side,
            "elapsed": elapsed,
            "total": self.step_total
        }

