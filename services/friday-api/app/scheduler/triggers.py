from enum import Enum
from typing import Optional

class TriggerType(str, Enum):
    ONCE = "ONCE"
    INTERVAL = "INTERVAL"
    CRON = "CRON"

class JobTrigger:
    """
    Defines interval and frequency rules for triggering scheduler jobs.

    TODO:
    - Support standard cron string syntax checks
    - Verify if trigger conditions match current local time slices
    - Track next scheduled execution epochs
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

    def should_fire(self, current_time: float) -> bool:
        """
        Determines if the trigger is ready to fire.

        Args:
            current_time (float): Current timestamp.

        Returns:
            bool: True if trigger criteria match.
        """
        # TODO: Compute trigger matching logic
        return False
