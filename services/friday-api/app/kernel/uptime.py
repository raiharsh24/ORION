import time
from datetime import timedelta


class KernelUptime:
    _start: float = 0.0

    @classmethod
    def start(cls) -> None:
        cls._start = time.monotonic()

    @classmethod
    def seconds(cls) -> float:
        if cls._start == 0.0:
            return 0.0
        return time.monotonic() - cls._start

    @classmethod
    def formatted(cls) -> str:
        return str(timedelta(seconds=int(cls.seconds())))
