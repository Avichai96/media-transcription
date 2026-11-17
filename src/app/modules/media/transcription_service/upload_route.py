"""Bound the multipart body before handing it to FastAPI's parser."""

import logging
from http import HTTPStatus

from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

from app.modules.media.transcription_service.constants import MAX_REQUEST_BYTES

logger = logging.getLogger(__name__)


class UploadRoute(APIRoute):
    """Reject oversized upload requests regardless of their framing.

    Check the declared length early and count bytes in the actual body stream.
    """

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["method"] != "POST":
            await super().handle(scope, receive, send)
            return

        detail = "The upload request exceeds the maximum allowed size."
        declared_size = Headers(scope=scope).get("content-length", "")
        if (
            declared_size.isascii()
            and declared_size.isdecimal()
            and self._is_oversized(declared_size)
        ):
            logger.info("event=upload_rejected reason=declared_body_too_large")
            response = JSONResponse(
                {"detail": detail}, status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE
            )
            await response(scope, receive, send)
            return

        received = 0

        async def receive_with_limit() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    logger.info("event=upload_rejected reason=streamed_body_too_large")
                    raise HTTPException(
                        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        detail=detail,
                    )
            return message

        await super().handle(scope, receive_with_limit, send)

    @staticmethod
    def _is_oversized(declared_size: str) -> bool:
        size = declared_size.lstrip("0")
        limit = str(MAX_REQUEST_BYTES)
        return (len(size), size) > (len(limit), limit)
