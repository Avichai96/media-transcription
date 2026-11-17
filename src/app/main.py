"""FastAPI entry point; run it with `uv run fastapi dev`."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.startup import add_middlewares, lifespan
from app.modules.media.router import router as media_router
from app.modules.media.upload_page_service.constants import STATIC_DIR

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
add_middlewares(app)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
    # A 5xx is the server's fault, so the error it was raised from goes in the log.
    if error.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        logger.error(
            "%s %s failed: %s",
            request.method,
            request.url.path,
            error.message,
            exc_info=error,
        )
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.message},
        headers=error.headers,
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, error: Exception) -> JSONResponse:
    # Starlette re-raises the error after this response, so the server still logs it.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/", include_in_schema=False)
async def index() -> RedirectResponse:
    return RedirectResponse("/media/upload")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(media_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
