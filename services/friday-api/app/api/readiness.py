from fastapi import APIRouter
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState
from app.kernel.uptime import KernelUptime

router = APIRouter(tags=["readiness"])


@router.get("/live")
async def liveness():
    """Simple liveness probe — always 200 if the process is alive."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness():
    """Deep readiness probe — verifies all subsystems are operational."""
    kernel = FridayKernel.get_instance()
    state = kernel.state()

    checks = {
        "kernel": state == KernelState.READY,
        "database": False,
        "memory": False,
        "runtime": False,
    }

    try:
        memory_engine = kernel.get_service("memory_engine")
        checks["memory"] = memory_engine is not None
    except Exception:
        pass

    try:
        runtime = kernel.get_service("mission_runtime") or kernel.get_service("workflow_runtime_manager")
        checks["runtime"] = runtime is not None
    except Exception:
        pass

    try:
        import sqlite3
        import os
        db_path = os.path.join(
            getattr(kernel._config.paths, "persist_dir", ".friday_kb"),
            "friday_memory.db",
        )
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            checks["database"] = True
    except Exception:
        pass

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "status": "ready" if all_ready else "not_ready",
        "kernel_state": state.value,
        "uptime_seconds": KernelUptime.seconds(),
        "checks": checks,
    }
