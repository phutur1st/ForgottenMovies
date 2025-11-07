import logging
import os
import signal
import time

from filelock import Timeout

from forgotten_movies import is_scheduler_disabled
from job_runner import JOB_LOCK_TIMEOUT, acquire_job_lock, execute_job

LOGGER = logging.getLogger("ForgottenMoviesScheduler")
LOGGER.setLevel(logging.INFO)

JOB_INTERVAL_SECONDS = int(os.getenv("JOB_INTERVAL_SECONDS", 600))
INITIAL_DELAY_SECONDS = int(os.getenv("INITIAL_DELAY_SECONDS", 600))
SLEEP_GRANULARITY = 1

_shutdown_requested = False
_disabled_notice_logged = False


def _request_shutdown(signum, frame) -> None:  # pragma: no cover - signal handler
    global _shutdown_requested
    LOGGER.info("Scheduler received signal %s; shutting down.", signum)
    _shutdown_requested = True


for _signal in (signal.SIGINT, signal.SIGTERM):  # pragma: no branch - trivial loop
    signal.signal(_signal, _request_shutdown)


def _sleep_with_interrupt(seconds: int) -> None:
    remaining = seconds
    while remaining > 0 and not _shutdown_requested:
        step = min(SLEEP_GRANULARITY, remaining)
        time.sleep(step)
        remaining -= step


def main() -> None:
    LOGGER.info(
        "Scheduler process starting (initial delay %s s, interval %s s).",
        INITIAL_DELAY_SECONDS,
        JOB_INTERVAL_SECONDS,
    )
    _sleep_with_interrupt(INITIAL_DELAY_SECONDS)

    global _disabled_notice_logged
    while not _shutdown_requested:
        if is_scheduler_disabled():
            if not _disabled_notice_logged:
                LOGGER.info("Scheduler disabled; skipping automated runs until re-enabled.")
                _disabled_notice_logged = True
        else:
            if _disabled_notice_logged:
                LOGGER.info("Scheduler re-enabled; resuming automated runs.")
                _disabled_notice_logged = False
            try:
                lock = acquire_job_lock(timeout=JOB_LOCK_TIMEOUT)
            except Timeout:
                LOGGER.info("Job already running; skipping automated run.")
            else:
                try:
                    execute_job("scheduled")
                finally:
                    lock.release()
        _sleep_with_interrupt(JOB_INTERVAL_SECONDS)

    LOGGER.info("Scheduler process exiting.")


if __name__ == "__main__":  # pragma: no cover - entrypoint
    main()
