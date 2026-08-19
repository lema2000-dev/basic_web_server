from basic_web_server import Request


def test_request_parsing():
    raw_request = (
        b"POST /test HTTP/1.1\r\n"
        b"Host: 127.0.0.1:5000\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"Hello"
    )

    request = Request(raw_request)

    assert request.method == "POST"
    assert request.target == "/test"
    assert request.version == "HTTP/1.1"

    assert request.headers["Host"] == "127.0.0.1:5000"
    assert request.headers["Content-Type"] == "text/plain"
    assert request.headers["Content-Length"] == "5"

    assert request.body == b"Hello"