import os
import time
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.scheduler.triggers import JobTrigger, TriggerType
from app.scheduler.jobs import ScheduledJob
from app.scheduler.scheduler import FridayScheduler

def test_once_trigger():
    trigger = JobTrigger(TriggerType.ONCE)
    now = time.time()
    
    # First check: should fire
    assert trigger.should_fire(now) is True
    # Second check: should NOT fire (prevent duplicate / once rule)
    assert trigger.should_fire(now) is False
    assert trigger.should_fire(now + 10) is False

def test_interval_trigger_and_drift_prevention():
    trigger = JobTrigger(TriggerType.INTERVAL, interval_seconds=10)
    now = time.time()
    
    # First check: fires immediately
    assert trigger.should_fire(now) is True
    
    # Intermediate checks: should NOT fire
    assert trigger.should_fire(now + 5) is False
    assert trigger.should_fire(now + 9.9) is False
    
    # Fires after interval
    assert trigger.should_fire(now + 10) is True
    
    # Next interval check
    assert trigger.should_fire(now + 15) is False
    
    # Fires with a drift (e.g. checked late at +23s)
    # It should align self.last_fired to +20s, and return True
    assert trigger.should_fire(now + 23) is True
    assert trigger.last_fired == now + 20
    
    # Since last_fired was aligned to +20, checking at +25 should return False
    assert trigger.should_fire(now + 25) is False
    # Checking at +30 should return True
    assert trigger.should_fire(now + 30) is True

def test_cron_trigger_parsing_and_matching():
    # Job scheduled to fire every 5 minutes: "*/5 * * * *"
    trigger = JobTrigger(TriggerType.CRON, cron_expression="*/5 * * * *")
    
    # 2026-06-28 12:00:00 local time
    dt_match = datetime(2026, 6, 28, 12, 0, 0).astimezone()
    epoch_match = dt_match.timestamp()
    
    # 2026-06-28 12:03:00 local time (not matching minutes)
    dt_no_match = datetime(2026, 6, 28, 12, 3, 0).astimezone()
    epoch_no_match = dt_no_match.timestamp()
    
    assert trigger.should_fire(epoch_match) is True
    # Verify duplicate prevention: checking same minute again
    assert trigger.should_fire(epoch_match + 10) is False
    
    # Verify no match
    assert trigger.should_fire(epoch_no_match) is False

def test_cron_trigger_complex_expressions():
    # Cron matching specific hours and range of weekdays: "0 12-14 * * 1-5" (12:00, 13:00, 14:00 on Monday-Friday)
    trigger = JobTrigger(TriggerType.CRON, cron_expression="0 12-14 * * 1-5")
    
    # Monday = 1 in python's dt.weekday()+1 % 7 (weekday() returns 0 for Monday. So dow = 1)
    # Test Monday 12:00:00 (Matches!)
    dt_match1 = datetime(2026, 6, 29, 12, 0, 0).astimezone() # June 29, 2026 is Monday
    assert trigger.should_fire(dt_match1.timestamp()) is True
    
    # Monday 13:00:00 (Matches!)
    dt_match2 = datetime(2026, 6, 29, 13, 0, 0).astimezone()
    assert trigger.should_fire(dt_match2.timestamp()) is True
    
    # Monday 15:00:00 (No match, hour 15 is outside range 12-14)
    dt_no_match1 = datetime(2026, 6, 29, 15, 0, 0).astimezone()
    assert trigger.should_fire(dt_no_match1.timestamp()) is False
    
    # Sunday 12:00:00 (No match, Sunday is DOW 0 or 7, outside range 1-5)
    dt_no_match2 = datetime(2026, 6, 28, 12, 0, 0).astimezone() # June 28, 2026 is Sunday
    assert trigger.should_fire(dt_no_match2.timestamp()) is False

def test_cron_trigger_sunday_normalization():
    # Test Sunday matches when DOW is 0 or 7
    trigger_0 = JobTrigger(TriggerType.CRON, cron_expression="0 12 * * 0")
    trigger_7 = JobTrigger(TriggerType.CRON, cron_expression="0 12 * * 7")
    
    dt_sunday = datetime(2026, 6, 28, 12, 0, 0).astimezone() # Sunday
    assert trigger_0.should_fire(dt_sunday.timestamp()) is True
    
    # Reset triggers to allow firing on same minute for testing
    trigger_7.last_fired_minute = None
    assert trigger_7.should_fire(dt_sunday.timestamp()) is True

def test_cron_trigger_comma_list():
    trigger = JobTrigger(TriggerType.CRON, cron_expression="0 9,12,18 * * *")
    
    dt_9 = datetime(2026, 6, 28, 9, 0, 0).astimezone()
    dt_12 = datetime(2026, 6, 28, 12, 0, 0).astimezone()
    dt_15 = datetime(2026, 6, 28, 15, 0, 0).astimezone()
    
    assert trigger.should_fire(dt_9.timestamp()) is True
    assert trigger.should_fire(dt_12.timestamp()) is True
    assert trigger.should_fire(dt_15.timestamp()) is False

@pytest.mark.anyio
async def test_scheduler_integration():
    scheduler = FridayScheduler()
    await scheduler.start()
    
    try:
        trigger = JobTrigger(TriggerType.INTERVAL, interval_seconds=1)
        job = ScheduledJob(
            job_id="test_integration_job",
            workflow_id="workflow_123",
            trigger=trigger
        )
        
        await scheduler.schedule_job(job)
        
        # Wait a short duration to let the tick loop process the job
        await asyncio.sleep(1.5)
        
        assert job.success_count >= 1
        assert job.last_run_timestamp is not None
    finally:
        await scheduler.stop()
