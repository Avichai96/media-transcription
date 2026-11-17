"""Errors raised by the upload page service; routes map each to an HTTP error."""

from app.modules.media.upload_page_service.types import UploadPageId


class UploadPageError(Exception):
    """Base of the upload page service's errors, which carry no HTTP status.

    Catch it to handle any of them; a route maps each to one of core/exceptions.
    """


class UploadPageNotFoundError(UploadPageError):
    """Raised when no upload page has the requested id.

    A route reports it as a 404 with this message.
    """

    def __init__(self, upload_page_id: UploadPageId) -> None:
        super().__init__(f"Upload page {upload_page_id} not found")
