from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

from . import db
from .machine_adapter import MockCNCAdapter


class QueueWorker:
    def __init__(self, poll_interval_seconds: float = 1.0) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._adapter = MockCNCAdapter()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        db.init_db()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="QueueWorker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._process_once()
            except Exception:
                time.sleep(self.poll_interval_seconds)
            time.sleep(self.poll_interval_seconds)

    def _process_once(self) -> None:
        next_job = db.get_next_queued_job()
        if not next_job:
            return

        job_id = next_job["id"]
        program_code = next_job["code_text"]
        est = next_job.get("estimated_duration_seconds")

        db.update_job_status(job_id, "running", machine_name=self._adapter.machine_name)

        def check_state() -> str:
            status = db.get_job_status(job_id)
            if status == "canceled":
                return "cancel"
            if status == "paused":
                return "pause"
            return "resume"

        try:
            duration = self._adapter.estimate_duration_seconds(est, program_code)
            self._adapter.execute(duration_seconds=duration, check_should_continue=check_state)
        except Exception as exc:
            final_status = db.get_job_status(job_id)
            if final_status != "canceled":
                db.update_job_status(job_id, "failed", error_message=str(exc))
            else:
                db.update_job_status(job_id, "canceled", error_message=str(exc))
            return

        db.update_job_status(job_id, "completed")