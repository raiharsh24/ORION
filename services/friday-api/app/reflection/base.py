from abc import ABC, abstractmethod

from app.reflection.models import ExecutionSnapshot, ReflectionReport


class BaseReflectionEngine(ABC):
    @abstractmethod
    def reflect(self, snapshot: ExecutionSnapshot) -> ReflectionReport:
        ...
