from typing import Protocol, runtime_checkable

@runtime_checkable
class AudioPlaybackController(Protocol):
    """
    Protocol definition for low-latency playback drivers and audio buffers control.
    """
    async def play(self) -> None:
        """Starts or resumes audio playback."""
        ...

    async def pause(self) -> None:
        """Pauses the current audio playback."""
        ...

    async def stop(self) -> None:
        """Immediately halts all playouts and clears output drivers buffers."""
        ...

    async def enqueue(self, audio_data: bytes) -> None:
        """Appends audio chunk data to playout queue."""
        ...

    async def clear_queue(self) -> None:
        """Flushes the current playout queue."""
        ...
