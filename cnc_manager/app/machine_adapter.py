from __future__ import annotations

import random
import time
from typing import Optional


class MockCNCAdapter:
    """A mock CNC machine that simulates job execution.

    In a real integration, replace methods here with actual CNC controller API calls.
    """

    def __init__(self, machine_name: str = "MockCNC-01") -> None:
        self.machine_name = machine_name

    def estimate_duration_seconds(self, estimated: Optional[int], code_text: str) -> int:
        if estimated and estimated > 0:
            return estimated
        # Very naive heuristic: 0.05s per char, capped between 5 and 60 seconds
        rough = int(len(code_text) * 0.05)
        return max(5, min(rough, 60))

    def execute(self, duration_seconds: int, check_should_continue) -> None:
        """Simulate execution for duration_seconds, periodically checking whether to pause/cancel."""
        end_time = time.time() + duration_seconds
        while time.time() < end_time:
            time.sleep(0.5)
            action = check_should_continue()
            if action == "cancel":
                raise RuntimeError("Job canceled by operator")
            if action == "pause":
                # Busy-wait with small sleeps until resumed or canceled
                while True:
                    time.sleep(0.5)
                    next_action = check_should_continue()
                    if next_action == "resume":
                        break
                    if next_action == "cancel":
                        raise RuntimeError("Job canceled by operator")
        # done