"""Errors that main.py turns into JSON responses, one class per HTTP status.

Routes raise them from their service's errors, and main.py logs each 5xx.
"""


class AppError(Exception):
    """An error the API reports to the client instead of a 500 traceback.

    main.py responds with status_code, headers and {"detail": message}.
    """

    status_code = 500

    def __init__(self, message: str, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.headers = headers


class BadRequestError(AppError):
    """Raised when a request is well-typed but cannot be acted on as sent.

    It is reported as 400 Bad Request.
    """

    status_code = 400


class UnauthorizedError(AppError):
    """Raised when a request has no valid credentials.

    It is reported as 401 Unauthorized with a WWW-Authenticate: Bearer header.
    """

    status_code = 401

    def __init__(self, message: str) -> None:
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    """Raised when the caller is known but not allowed to do this.

    It is reported as 403 Forbidden.
    """

    status_code = 403


class NotFoundError(AppError):
    """Raised when a requested resource does not exist.

    A route raises it from its service's error, for example OrderNotFoundError.
    """

    status_code = 404


class ConflictError(AppError):
    """Raised when a write clashes with existing data, such as a duplicate.

    It is reported as 409 Conflict.
    """

    status_code = 409


class UnprocessableContentError(AppError):
    """Raised when a valid request breaks a business rule, such as a past due date.

    It is reported as 422 Unprocessable Content, the status of FastAPI's own
    validation errors.
    """

    status_code = 422


class TooManyRequestsError(AppError):
    """Raised when a caller goes over a rate limit.

    It is reported as 429 Too Many Requests, with Retry-After when given.
    """

    status_code = 429

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        headers = None if retry_after is None else {"Retry-After": str(retry_after)}
        super().__init__(message, headers=headers)


class BadGatewayError(AppError):
    """Raised when a service the app calls answers with an error.

    It is reported as 502 Bad Gateway.
    """

    status_code = 502


class ServiceUnavailableError(AppError):
    """Raised when the app or a service it needs is down or overloaded.

    It is reported as 503 Service Unavailable, with Retry-After when given.
    """

    status_code = 503

    def __init__(self, message: str, *, retry_after: int | None = None) -> None:
        headers = None if retry_after is None else {"Retry-After": str(retry_after)}
        super().__init__(message, headers=headers)


class GatewayTimeoutError(AppError):
    """Raised when a service the app calls does not answer in time.

    It is reported as 504 Gateway Timeout.
    """

    status_code = 504


class PayloadTooLargeError(AppError):
    """Report a request payload above the configured byte limit.

    It is reported as 413 Content Too Large.
    """

    status_code = 413
