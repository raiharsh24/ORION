from enum import Enum
from typing import Optional, List, Any
from datetime import datetime, timezone
import time
from loguru import logger

class TriggerType(str, Enum):
    ONCE = "ONCE"
    INTERVAL = "INTERVAL"
    CRON = "CRON"


def match_cron_field(val: int, pattern: str, min_val: int, max_val: int) -> bool:
    if pattern == "*":
        return True
    
    if "," in pattern:
        return any(match_cron_field(val, p, min_val, max_val) for p in pattern.split(","))
        
    step = 1
    if "/" in pattern:
        base, step_str = pattern.split("/", 1)
        step = int(step_str)
        pattern = base
        
    if pattern == "*":
        return (val - min_val) % step == 0
        
    if "-" in pattern:
        start_str, end_str = pattern.split("-", 1)
        start = int(start_str)
        end = int(end_str)
        if start <= val <= end:
            return (val - start) % step == 0
        return False
        
    try:
        exact = int(pattern)
        return val == exact and (val - exact) % step == 0
    except ValueError:
        logger.warning(f"Invalid cron field integer token: '{pattern}'")
        return False


def match_cron_dow(val: int, pattern: str) -> bool:
    # Normalize day of week (Sunday is 0, standard cron might have 7 as Sunday)
    pattern = pattern.replace("7", "0")
    return match_cron_field(val, pattern, 0, 6)


class JobTrigger:
    """
    Defines interval and frequency rules for triggering scheduler jobs.
    """
    def __init__(
        self,
        trigger_type: TriggerType,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None
    ) -> None:
        self.trigger_type = trigger_type
        self.interval_seconds = interval_seconds
        self.cron_expression = cron_expression
        self.last_fired: Optional[float] = None
        self.last_fired_minute: Optional[tuple] = None

    def should_fire(self, current_time: float) -> bool:
        """
        Determines if the trigger is ready to fire.

        Args:
            current_time (float): Current timestamp.

        Returns:
            bool: True if trigger criteria match.
        """
        try:
            if self.trigger_type == TriggerType.ONCE:
                return self._should_fire_once(current_time)
            elif self.trigger_type == TriggerType.INTERVAL:
                return self._should_fire_interval(current_time)
            elif self.trigger_type == TriggerType.CRON:
                return self._should_fire_cron(current_time)
            else:
                logger.warning(f"Unknown trigger type: {self.trigger_type}")
                return False
        except Exception as e:
            logger.error(f"Error checking trigger fire condition: {e}")
            return False

    def _should_fire_once(self, current_time: float) -> bool:
        if self.last_fired is None:
            self.last_fired = current_time
            return True
        return False

    def _should_fire_interval(self, current_time: float) -> bool:
        if self.interval_seconds is None or self.interval_seconds <= 0:
            return False
            
        if self.last_fired is None:
            # Fire on the first check after scheduling
            self.last_fired = current_time
            return True
            
        if current_time - self.last_fired >= self.interval_seconds:
            # Prevent firing multiple times in the same tick by updating last_fired
            # Adjust last_fired to prevent scheduler drift by increments of interval
            intervals_elapsed = int((current_time - self.last_fired) // self.interval_seconds)
            self.last_fired += intervals_elapsed * self.interval_seconds
            return True
        return False

    def _should_fire_cron(self, current_time: float) -> bool:
        if not self.cron_expression:
            return False
            
        # Ensure we are checking with local system timezone (timezone-aware)
        dt = datetime.fromtimestamp(current_time).astimezone()
        current_min_id = (dt.year, dt.month, dt.day, dt.hour, dt.minute)
        
        # Prevent double trigger in the same minute
        if self.last_fired_minute == current_min_id:
            return False
            
        parts = self.cron_expression.strip().split()
        if len(parts) != 5:
            logger.error(f"Invalid cron expression pattern: '{self.cron_expression}'")
            return False
            
        min_pat, hour_pat, day_pat, month_pat, dow_pat = parts
        
        # Calculate time fields
        minute = dt.minute
        hour = dt.hour
        day = dt.day
        month = dt.month
        # dt.weekday() is 0=Monday, ..., 6=Sunday. Map to 0=Sunday, 1=Monday, ..., 6=Saturday
        dow = (dt.weekday() + 1) % 7
        
        if (match_cron_field(minute, min_pat, 0, 59) and
            match_cron_field(hour, hour_pat, 0, 23) and
            match_cron_field(day, day_pat, 1, 31) and
            match_cron_field(month, month_pat, 1, 12) and
            match_cron_dow(dow, dow_pat)):
            
            self.last_fired = current_time
            self.last_fired_minute = current_min_id
            return True
            
        return False

