"""AyuDrishti API application.

Wiring only. Every piece of behaviour lives in ``backend/services`` or in the
framework-independent ``ai`` package, so the assessment engine can be used
(and tested) without starting a web server.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Allow `python backend/main.py` and `uvicorn backend.main:app` from the repo
# root without requiring the project to be pip-installed first.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai.pose_assessment.rules import RuleConfigError

from backend.api import (
    asanas,
    assessment,
    assistant,
    auth,
    progress,
    recommendations,
    sessions,
    users,
)
from backend.core.config import settings
from backend.database.seed import init_db
from backend.services.engines import get_registry

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ayudrishti")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database and validate the asana library on startup.

    Loading the rule files eagerly means a malformed asana definition fails
    the deploy instead of surfacing mid-session as a 500 on someone's mat.
    """
    try:
        registry = get_registry()
        logger.info(
            "Loaded %d asanas (%d alignment rules).",
            len(registry),
            sum(len(c.rules) for c in registry.all()),
        )
    except (RuleConfigError, FileNotFoundError) as exc:
        logger.error("Asana rule library failed to load: %s", exc)
        raise

    count = init_db()
    logger.info("Database ready at %s (%d asanas seeded).", _safe_db_url(), count)
    yield


def _safe_db_url() -> str:
    """Database URL with any password redacted, for logging."""
    url = settings.database_url
    if "@" in url and "//" in url:
        scheme, rest = url.split("//", 1)
        creds, host = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}//{user}:***@{host}"
    return url


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AyuDrishti is a closed-loop AI yoga platform: it recommends asanas from "
        "your goals and history, assesses your posture in real time against "
        "pose-specific alignment rules, explains how to correct deviations, "
        "tracks your progress and adapts future practice."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    users.router,
    asanas.router,
    recommendations.router,
    sessions.router,
    assessment.router,
    progress.router,
    assistant.router,
):
    app.include_router(router, prefix=settings.api_prefix)

# Wearables are registered separately to make the optionality explicit: the
# core loop never calls into this router.
from backend.api import wearables  # noqa: E402

app.include_router(wearables.router, prefix=settings.api_prefix)


@app.exception_handler(RuleConfigError)
async def _rule_config_error(_request, exc: RuleConfigError) -> JSONResponse:
    logger.error("Pose rule configuration error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "A pose rule definition is invalid. Check the server logs."},
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    registry = get_registry()
    return {
        "status": "ok",
        "version": settings.app_version,
        "asanas": len(registry),
        "rules": sum(len(c.rules) for c in registry.all()),
        "database": "postgresql" if settings.is_postgres else "sqlite (development)",
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":  # pragma: no cover - manual entry point
    import uvicorn

    uvicorn.run(
        "backend.main:app", host="0.0.0.0", port=8000, reload=settings.debug
    )
