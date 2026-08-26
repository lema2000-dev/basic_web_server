class HTTPError(Exception):
    status_code = 500
    reason = "Internal Server Error"

    def __init__(self, message="", close_connection=False):
        super().__init__(message)
        self.close_connection = close_connection


# HTTP-level errors that can be converted directly into error responses.
class BadRequestError(HTTPError):
    status_code = 400
    reason = "Bad Request"


class RequestTimeoutError(HTTPError):
    status_code = 408
    reason = "Request Timeout"


class RequestTooLargeError(HTTPError):
    status_code = 413
    reason = "Content Too Large"


class HTTPVersionNotSupportedError(HTTPError):
    status_code = 505
    reason = "HTTP Version Not Supported"


class InternalServerError(HTTPError):
    status_code = 500
    reason = "Internal Server Error"


class ApplicationError(InternalServerError):
    pass


# Non-HTTP errors are handled without sending an HTTP response.
class ClientConnectionError(Exception):
    pass


class ConfigurationError(Exception):
    pass