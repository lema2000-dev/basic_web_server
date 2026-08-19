from .http import CRLF, STATUS_REASONS

class Response:
    def __init__(self, body, status_code=200, content_type="text/html"):
        self.status_code = status_code
        self.content_type = content_type
        self.body = body

    def to_bytes(self):
        body_bytes = self.body.encode("utf-8")

        status_text = STATUS_REASONS.get(self.status_code, "Unknown Status")

        response_head = (
            f"HTTP/1.1 {self.status_code} {status_text}{CRLF}"
            f"Content-Type: {self.content_type}{CRLF}"
            f"Content-Length: {len(body_bytes)}{CRLF}"
            f"Connection: close{CRLF}"
            f"{CRLF}"
        )

        return response_head.encode("utf-8") + body_bytes