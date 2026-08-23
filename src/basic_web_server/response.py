from .exceptions import ApplicationError

from .http import CRLF, STATUS_REASONS

class Response:
    def __init__(self, body=b"", status_code=200, headers=None):
        if not isinstance(body, (str, bytes)):
            raise ApplicationError("Response body must be of type str or bytes.")

        if not isinstance(status_code, int):
            raise ApplicationError("Status code must be an integer.")
        if not (100 <= status_code <= 599):
            raise ApplicationError("Response status code must be between 100 and 599.")

        if headers is None:
            normalized_headers = []
        elif isinstance(headers, dict):
            normalized_headers = list(headers.items())
        else:
            try:
                normalized_headers = list(headers)
            except TypeError as error:
                raise ApplicationError("Response headers must be a dict or an iterable of (name, value) pairs.") from error

        for header in normalized_headers:
            if not isinstance(header, (tuple, list)) or len(header) != 2:
                raise ApplicationError("Each response header must be a (name, value) pair.")
            name, value = header
            if not isinstance(name, str):
                raise ApplicationError("Response header name must be a string.")
            if not isinstance(value, str):
                raise ApplicationError("Response header value must be a string.")
            if "\r" in name or "\n" in name:
                raise ApplicationError("Response header name must not contain carriage return or line feed characters.")
            if "\r" in value or "\n" in value:
                raise ApplicationError("Response header value must not contain carriage return or line feed characters.")
            if name.lower() == "content-length":
                raise ApplicationError("Content-Length header is managed by the server and must not be provided by the application.")

        self.headers = [(name, value) for name, value in normalized_headers]

        self.status_code = status_code

        if isinstance(body, str):
            self.body = body.encode("utf-8")
        else:
            self.body = body


    def to_bytes(self):
        status_text = STATUS_REASONS.get(self.status_code, "")

        headers = list(self.headers)
        headers.append(("Content-Length", str(len(self.body))))

        status_line = f"HTTP/1.1 {self.status_code}"

        if status_text:
            status_line += f" {status_text}"

        status_line += CRLF

        response_head = status_line

        for name, value in headers:
            response_head += f"{name}: {value}{CRLF}"

        response_head += CRLF

        return response_head.encode("utf-8") + self.body
