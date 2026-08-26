class HTTPError(Exception):
    status_code = 500
    reason = "Internal Server Error"

    def __init__(self, message="", close_connection=False):
        super().__init__(message)
        self.close_connection = close_connection

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

class ClientConnectionError(Exception):
    pass

