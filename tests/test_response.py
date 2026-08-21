from basic_web_server.response import Response


def test_response_to_bytes():
    response = Response(
        "Hello",
        status_code=200,
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

    response_data = response.to_bytes()

    expected = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"Hello"
    )

    assert response_data == expected