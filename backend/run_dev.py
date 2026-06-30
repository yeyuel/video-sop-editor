from __future__ import annotations

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    reload = settings.app_env.strip().lower() in {"development", "dev", "local"}
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=reload,
        timeout_graceful_shutdown=max(1, int(settings.app_graceful_shutdown_sec)),
    )
