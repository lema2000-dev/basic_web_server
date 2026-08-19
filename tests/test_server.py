from basic_web_server import Response, Server


class FakeSocket:

    def __init__(self, chunks):
        self.chunks = chunks

    def recv(self, buffer_size):
        if not self.chunks:
            return b""

        chunk = self.chunks[0]

        data = chunk[:buffer_size]
        remaining = chunk[buffer_size:]

        if remaining:
            self.chunks[0] = remaining
        else:
            self.chunks.pop(0)

        return data

def application(request):
    return Response("Hello")

def test_receive_http_request():
    server = Server(application)

    fake_socket = FakeSocket([
        b"GET /test HTTP/1.1\r\n",
        b"Host: localhost\r\n",
        b"\r\n",
    ])

    received_data = server._receive_http_request(
        fake_socket
    )

    expected_data = (
        b"GET /test HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    assert received_data == expected_data

def test_receive_http_request_with_body():
    server = Server(application)

    fake_socket = FakeSocket([
        (
            b"POST /test HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
            b"Hello"
        ),
        b" ",
        b"World",
    ])

    received_data = server._receive_http_request(
        fake_socket
    )

    expected_data = (
        b"POST /test HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: 11\r\n"
        b"\r\n"
        b"Hello World"
    )

    assert received_data == expected_data