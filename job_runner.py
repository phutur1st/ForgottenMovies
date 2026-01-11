import os
from datetime import datetime
from typing import Optional

from filelock import FileLock, Timeout
from tinydb import TinyDB, Query

from forgotten_movies import (
    DATA_DIR,
    flush_log_handlers,
    logger as forgotten_logger,
    main as run_forgotten_movies_job,
)

JOB_LOCK_PATH = os.path.join(DATA_DIR, "job.lock")
JOB_LOCK_TIMEOUT = float(os.getenv("JOB_LOCK_TIMEOUT", "0.1"))

# Jobs database - stores job execution history for dashboard
jobs_db = TinyDB(os.path.join(DATA_DIR, "jobs.json"))


def _save_job_status(reason: str, success: bool, error_message: str = None) -> None:
    """
    Save job execution record to jobs DB.
    Stores execution history for future dashboard features.
    """
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "reason": reason,
        "success": success,
        "error_message": error_message
    }
    try:
        jobs_db.insert(record)
        # Keep last 100 job executions to prevent unbounded growth
        all_records = jobs_db.all()
        if len(all_records) > 100:
            # Remove oldest records
            for old_record in sorted(all_records, key=lambda x: x.get("timestamp", ""))[:-100]:
                jobs_db.remove(doc_ids=[old_record.doc_id])
    except Exception as exc:
        forgotten_logger.warning("Failed to save job status: %s", exc)


def get_last_job_status() -> dict:
    """Get the most recent job execution status from jobs DB."""
    try:
        records = jobs_db.all()
        if records:
            # Return most recent by timestamp
            return max(records, key=lambda x: x.get("timestamp", ""))
    except Exception as exc:
        forgotten_logger.warning("Failed to read job status: %s", exc)
    return None


def execute_job(reason: str) -> None:
    """
    Run the Forgotten Movies workflow and ensure logs are flushed afterward.
    """
    forgotten_logger.info("Forgotten Movies job triggered (%s).", reason)
    try:
        run_forgotten_movies_job()
        forgotten_logger.info("Forgotten Movies job completed (%s).", reason)
        _save_job_status(reason, success=True)
    except Exception as exc:  # pragma: no cover - defensive logging
        error_msg = str(exc)
        forgotten_logger.exception("Forgotten Movies job raised an exception (%s).", reason)
        _save_job_status(reason, success=False, error_message=error_msg)
    finally:
        flush_log_handlers()


def acquire_job_lock(timeout: Optional[float] = JOB_LOCK_TIMEOUT) -> FileLock:
    """
    Acquire and return the inter-process job lock.
    """
    # Use a non-thread-local lock so the holder can release it from worker threads.
    lock = FileLock(JOB_LOCK_PATH, thread_local=False)
    lock.acquire(timeout=timeout)
    return lock


def try_execute_job(reason: str, timeout: Optional[float] = JOB_LOCK_TIMEOUT) -> bool:
    """
    Attempt to execute the job, returning False if the lock could not be acquired.
    """
    lock = FileLock(JOB_LOCK_PATH, thread_local=False)
    try:
        lock.acquire(timeout=timeout)
    except Timeout:
        return False
    try:
        execute_job(reason)
    finally:
        lock.release()
    return True
