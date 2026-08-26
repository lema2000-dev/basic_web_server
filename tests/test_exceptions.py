from basic_web_server.exceptions import (
    BadRequestError,
    HTTPError,
    HTTPVersionNotSupportedError,
    RequestTimeoutError,
    RequestTooLargeError,
)

def test_http_error():
    errors =  [
        (BadRequestError, 400, "Bad Request"),
        (RequestTimeoutError, 408, "Request Timeout"),
        (RequestTooLargeError, 413, "Content Too Large"),
        (HTTPVersionNotSupportedError, 505, "HTTP Version Not Supported"),
    ]

    for error, status_code, reason in errors:
        assert isinstance(error(), HTTPError)
        assert error.status_code == status_code
        assert error.reason == reason

def test_http_error_message():
    error = BadRequestError("Custom error message")
    assert str(error) == "Custom error message"

def test_http_error_close_connection_true():
    error = BadRequestError("Custom error message", close_connection=True)
    assert error.close_connection is True

def test_http_error_close_connection_false():
    error = BadRequestError("Custom error message")
    assert error.close_connection is False

