from enum import Enum

class KernelState(str, Enum):
    """
    Defines the current lifecycle states of the central ORION system kernel.
    """
    BOOTING = "BOOTING"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    BUSY = "BUSY"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
