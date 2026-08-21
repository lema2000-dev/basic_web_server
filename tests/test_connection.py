import socket

from basic_web_server import ServerConfig
from basic_web_server.connection import ClientConnection

def application(request):
    return (
        f"Response for {request.target}",
        200,
        {
            "Content-Type": "text/plain; charset=utf-8",
        },
    )

TEST_CONFIG = ServerConfig(
    client_timeout=10.0,
    accept_timeout=0.5,
    recv_buffer_size=4096,
    max_request_size=1_048_576,
)

class FakeSocket:
    def __init__(self, chunks):
        self.chunks = chunks
        self.sent_data = []
        self.timeout = None
        self.recv_sizes = []

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, buffer_size):
        self.recv_sizes.append(buffer_size)
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

    def sendall(self, data):
        self.sent_data.append(data)

class TimeoutSocket(FakeSocket):
    def recv(self, buffer_size):
        raise socket.timeout("Simulated timeout")

def test_two_requests_in_single_chunk():
    raw_data = (
        b"GET /first HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
        b"GET /second HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    first_request_data = connection._receive_http_request()

    expected_first_request = (
        b"GET /first HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    assert first_request_data == expected_first_request

    expected_remaining = (
        b"GET /second HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    assert connection.buffer == expected_remaining

    second_request = connection._receive_http_request()

    assert second_request == expected_remaining
    assert connection.buffer == b""

def test_connection_close_stops_after_response():
    raw_data = (
        b"GET /first HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Connection: close\r\n"
        b"\r\n"
        b"GET /second HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    connection.handle()

    assert len(fake_socket.sent_data) == 1

    assert b"Response for /first" in fake_socket.sent_data[0]

def test_connection_handles_multiple_requests():
    raw_data = (
        b"GET /first HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
        b"GET /second HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Connection: close\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=application,
        config=TEST_CONFIG
    )

    connection.handle()

    assert len(fake_socket.sent_data) == 2

    assert b"Response for /first" in fake_socket.sent_data[0]
    assert b"Response for /second" in fake_socket.sent_data[1]

def test_connection_timeout_stops_handling():
    fake_socket = TimeoutSocket([])

    config = ServerConfig(client_timeout=3.5)

    connection = ClientConnection(fake_socket, "fake_address", application, config)
    connection.handle()

    assert fake_socket.timeout == 3.5
    assert fake_socket.sent_data == []

def test_make_response_from_body_and_status():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    response = connection._make_response(("Not Found", 404))

    assert response.status_code == 404
    assert response.body == b"Not Found"
    assert response.headers == []

def test_make_response_with_dict_headers():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    response = connection._make_response(
        ("Hello", 200, {"Content-Type": "text/plain", "X-Test": "example"})
    )

    assert response.status_code == 200
    assert response.body == b"Hello"

    assert response.headers == [
        ("Content-Type", "text/plain"),
        ("X-Test", "example")
    ]

def test_make_response_with_duplicate_headers():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    response = connection._make_response(
        (
            "Hello",
            200,
            [
                ("Content-Type", "text/plain"),
                ("Set-Cookie", "session=abc"),
                ("Set-Cookie", "language=hu")
            ]
        )
    )

    assert response.status_code == 200
    assert response.body == b"Hello"
    assert response.headers == [
        ("Content-Type", "text/plain"),
        ("Set-Cookie", "session=abc"),
        ("Set-Cookie", "language=hu")
    ]

def test_connection_uses_configured_recv_buffer_size():
    raw_data = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])

    config = ServerConfig(
        recv_buffer_size=128,
    )

    connection = ClientConnection(
        fake_socket,
        "fake_address",
        application,
        config,
    )

    connection._receive_http_request()

    assert fake_socket.recv_sizes[0] == 128