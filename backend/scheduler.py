import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None

async def cleanup_past_events() -> None:
    """
    Soft-delete events that have already occurred and aren't deleted.

    Queries `events` colelction for documents where `date < now` and
    `is_deleted` is False, then sets `is_deleted` to True and records
    `deleted_at` timestamp for those documents. 

    This function is called by the scheduler on a fixed interval. It imports the database client
    lazily so it can be registered at the module level before the database client is fully initialized.
    """
    from database import get_database

    try:
        db = get_database()
    except RuntimeError:
        logger.warning("[Scheduler] Database not ready yet, skipping cleanup")
        return
    
    now = datetime.now(timezone.utc)
    result = await db["events"].update_many(
        {"date": {"$lt": now}, "is_deleted": False},
        {"$set": {"is_deleted": True, "deleted_at": now}}
    )

    if result.modified_count:
        logger.info(f"[Scheduler] Soft-deleted {result.modified_count} past event(s)")

def create_scheduler() -> AsyncIOScheduler:
    """
    Build and configure the AsyncIOScheduler instance with the cleanup job.

    Returns:
        AsyncIOScheduler: The configured scheduler instance ready to be started.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Run the cleanup job every hour
    scheduler.add_job(
        cleanup_past_events,
        trigger="interval",
        hours=1,
        id="cleanup_past_events",
        name="Soft-delete past events",
        replace_existing=True
    )

    return scheduler

def start_scheduler() -> AsyncIOScheduler:
    """
    Create and start the background scheduler if it's not already running.

    Should be called once during application startup, after the database client is initialized and ready.

    Returns:
        AsyncIOScheduler: The running scheduler instance.
    """
    global _scheduler
    _scheduler = create_scheduler()
    _scheduler.start()
    logger.info("[Scheduler] Background scheduler started. Jobs: %s", [job.id for job in _scheduler.get_jobs()])
    return _scheduler

def stop_scheduler() -> None:
    """
    Gracefully shut down the background scheduler if it's running.

    Should be called during application shutdown to ensure any in-flight jobs complete before the application exits.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped")