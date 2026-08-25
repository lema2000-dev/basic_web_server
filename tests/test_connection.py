import socket
from typing import Mapping

import pytest

from basic_web_server import ServerConfig
from basic_web_server import connection
from basic_web_server.connection import ClientConnection
from basic_web_server.exceptions import BadRequestError, RequestTimeoutError, RequestTooLargeError

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

class SendErrorSocket(FakeSocket):
    def sendall(self, data):
        raise BrokenPipeError("Simulated broken pipe")

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

def test_receive_http_request_returns_none_on_clean_eof():
    fake_socket = FakeSocket([])

    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    result = connection._receive_http_request()

    assert result is b""

def test_receive_http_request_raises_on_incomplete_request():
    raw_data = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(BadRequestError) as error_info:
        connection._receive_http_request()

    assert "Client closed connection before completing the HTTP request." in str(error_info.value)

def test_receive_http_request_raises_on_incomplete_body():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: 10\r\n"
        b"\r\n"
        b"12345"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(BadRequestError) as error_info:
        connection._receive_http_request()

    assert "Client closed connection before completing the HTTP request body." in str(error_info.value)

def test_receive_http_request_raises_on_invalid_content_length():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: invalid\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(BadRequestError) as error_info:
        connection._receive_http_request()

    assert "Invalid Content-Length header value." in str(error_info.value)

def test_receive_http_request_raises_on_negative_content_length():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: -5\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(BadRequestError) as error_info:
        connection._receive_http_request()

    assert "Content-Length cannot be negative." in str(error_info.value)

def test_receive_http_request_raises_on_header_exceeding_max_size():
    raw_data = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        + b"A" * (TEST_CONFIG.max_request_size + 1)
        + b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(RequestTooLargeError) as error_info:
        connection._receive_http_request()

    assert error_info.value.close_connection is True
    assert error_info.value.status_code == 431

def test_receive_http_request_raises_when_body_exceeds_max_size():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length:" + str(TEST_CONFIG.max_request_size + 1).encode() + b"\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(RequestTooLargeError) as error_info:
        connection._receive_http_request()

    assert error_info.value.close_connection is True
    assert error_info.value.status_code == 431

def test_idle_connection_timeout_returns_empty():
    fake_socket = TimeoutSocket([])

    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    result = connection._receive_http_request()

    assert result == b""

class TimeoutAfterChunksSocket(FakeSocket):

    def recv(self, buffer_size):
        if self.chunks:
            return super().recv(buffer_size)

        raise socket.timeout("Simulated timeout after chunks")

def test_timeout_during_incomplete_header():
    raw_data = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
    )

    fake_socket = TimeoutAfterChunksSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(RequestTimeoutError) as error_info:
        connection._receive_http_request()

    assert error_info.value.close_connection is True
    assert error_info.value.status_code == 408

def test_timeout_during_incomplete_body():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: 10\r\n"
        b"\r\n"
        b"12345"
    )

    fake_socket = TimeoutAfterChunksSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(RequestTimeoutError) as error_info:
        connection._receive_http_request()

    assert error_info.value.close_connection is True
    assert error_info.value.status_code == 408

def test_receive_http_request_raises_on_multiple_content_length_headers():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: 5\r\n"
        b"Content-Length: 10\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(BadRequestError) as error_info:
        connection._receive_http_request()

    assert "Multiple Content-Length headers are not allowed." in str(error_info.value)
    assert error_info.value.close_connection is True

def test_receive_http_request_rejects_duplicate_equal_content_length():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: 5\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
    )   

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(BadRequestError) as error_info:
        connection._receive_http_request()

    assert "Multiple Content-Length headers are not allowed." in str(error_info.value)
    assert error_info.value.close_connection is True

def test_make_response_from_body():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    response = connection._make_response("Hello World")

    assert response.status_code == 200
    assert response.body == b"Hello World"
    assert response.headers == []

def test_make_response_from_body_and_status():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    response = connection._make_response(("Not Found", 404))

    assert response.status_code == 404
    assert response.body == b"Not Found"
    assert response.headers == []

def test_make_response_from_body_status_and_headers():
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

def test_make_response_raises_on_invalid_tuple_length():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG)

    with pytest.raises(Exception) as error_info:
        connection._make_response(("Hello", 200, {"Content-Type": "text/plain"}, "extra"))

    assert "Application must return body, (body, status_code) or (body, status_code, headers) tuple." in str(error_info.value)

def test_connection_stops_after_sendall_error():
    raw_data = (
        b"GET /first HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
        b"GET /second HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    fake_socket = SendErrorSocket([raw_data])

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=application,
        config=TEST_CONFIG
    )

    connection.handle()

    assert (
        b"GET /second HTTP/1.1" in connection.buffer
    )