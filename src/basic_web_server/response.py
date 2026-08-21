from .http import CRLF, STATUS_REASONS

class Response:
    def __init__(self, body=b"", status_code=200, headers=None):
        self.status_code = status_code
        if headers is None:
            self.headers = []
        elif isinstance(headers, dict):
            self.headers = list(headers.items())
        else:
            self.headers = list(headers)

        if isinstance(body, str):
            self.body = body.encode("utf-8")
        elif isinstance(body, bytes):
            self.body = body
        else:
            raise TypeError("Body must be of type str or bytes")


    def to_bytes(self):
        status_text = STATUS_REASONS[self.status_code]

        headers = list(self.headers)
        headers.append(("Content-Length", str(len(self.body))))

        response_head = (
            f"HTTP/1.1 "
            f"{self.status_code} "
            f"{status_text}"
            f"{CRLF}"
        )

        for name, value in headers:
            response_head += f"{name}: {value}{CRLF}"

        response_head += CRLF

        return response_head.encode("utf-8") + self.body

    def test_response_with_bytes_body():
        response = Response(
            b"\x00\x01\x02",
            status_code=200,
            headers={
                "Content-Type": "application/octet-stream",
            },
        )

        response_data = response.to_bytes()

        assert b"Content-Length: 3\r\n" in response_data
        assert response_data.endswith(b"\x00\x01\x02")

    def test_response_with_duplicate_headers():
        response = Response(
            "Hello",
            status_code=200,
            headers=[
                ("Set-Cookie", "session=abc"),
                ("Set-Cookie", "language=hu"),
            ],
        )

        response_data = response.to_bytes()

        assert (
            b"Set-Cookie: session=abc\r\n"
            b"Set-Cookie: language=hu\r\n"
            in response_data
        )