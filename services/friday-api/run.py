import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    # Bootstrap uvicorn with host/port mapping
    # Reload is active in Debug mode
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
