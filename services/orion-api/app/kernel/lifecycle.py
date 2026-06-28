from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.events.events import OrionEvent

class KernelLifecycleEvent(OrionEvent):
    """
    Base class for all Kernel lifecycle event types.
    """
    def __init__(self, topic: str, data: Dict[str, Any]) -> None:
        super().__init__(topic, data)

class KernelBooting(KernelLifecycleEvent):
    """
    Triggered when the boot manager sequence begins loading configurations.
    """
    def __init__(self, timestamp: Optional[float] = None) -> None:
        super().__init__(
            "KernelBooting",
            {"timestamp": timestamp or datetime.now(timezone.utc).timestamp()}
        )

class KernelReady(KernelLifecycleEvent):
    """
    Triggered when all system services are fully registered and validated.
    """
    def __init__(self, timestamp: Optional[float] = None) -> None:
        super().__init__(
            "KernelReady",
            {"timestamp": timestamp or datetime.now(timezone.utc).timestamp()}
        )

class KernelBusy(KernelLifecycleEvent):
    """
    Triggered when the kernel begins orchestrating a user mission or workflow task.
    """
    def __init__(self, mission_id: str) -> None:
        super().__init__(
            "KernelBusy",
            {"mission_id": mission_id, "timestamp": datetime.now(timezone.utc).timestamp()}
        )

class KernelShutdown(KernelLifecycleEvent):
    """
    Triggered when the kernel initiates a shutdown teardown protocol.
    """
    def __init__(self, reason: str) -> None:
        super().__init__(
            "KernelShutdown",
            {"reason": reason, "timestamp": datetime.now(timezone.utc).timestamp()}
        )

class KernelRestart(KernelLifecycleEvent):
    """
    Triggered when the kernel initiates a restart/reboot sequence.
    """
    def __init__(self, timestamp: Optional[float] = None) -> None:
        super().__init__(
            "KernelRestart",
            {"timestamp": timestamp or datetime.now(timezone.utc).timestamp()}
        )

class KernelError(KernelLifecycleEvent):
    """
    Triggered when the kernel encounters a fatal system-wide error.
    """
    def __init__(self, error_message: str, timestamp: Optional[float] = None) -> None:
        super().__init__(
            "KernelError",
            {
                "error": error_message,
                "timestamp": timestamp or datetime.now(timezone.utc).timestamp()
            }
        )

class ServiceRegistered(KernelLifecycleEvent):
    """
    Triggered when a dependency is registered within the central registry.
    """
    def __init__(self, service_name: str, service_class: str) -> None:
        super().__init__(
            "ServiceRegistered",
            {"service_name": service_name, "service_class": service_class}
        )

class ServiceStarted(KernelLifecycleEvent):
    """
    Triggered when a service successfully starts and transitions to ready.
    """
    def __init__(self, service_name: str) -> None:
        super().__init__("ServiceStarted", {"service_name": service_name})

class ServiceStopped(KernelLifecycleEvent):
    """
    Triggered when a service gracefully stops and releases resources.
    """
    def __init__(self, service_name: str) -> None:
        super().__init__("ServiceStopped", {"service_name": service_name})

class ServiceFailed(KernelLifecycleEvent):
    """
    Triggered when a service encounters a fatal initialization or processing error.
    """
    def __init__(self, service_name: str, error_message: str) -> None:
        super().__init__(
            "ServiceFailed",
            {"service_name": service_name, "error": error_message}
        )
