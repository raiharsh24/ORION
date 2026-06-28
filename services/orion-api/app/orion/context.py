from pydantic import BaseModel, Field
import time

class SystemContext(BaseModel):
    """
    Encapsulates current system metrics, timestamps, and platform meta.
    """
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of request processing")
    platform: str = Field(default="ORION OS v0.3", description="Active operating system layout")
    status: str = Field(default="nominal", description="Subsystem health status")
