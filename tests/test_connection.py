import socket
from typing import Mapping

import pytest
import logging

from basic_web_server import ServerConfig
from basic_web_server import connection
from basic_web_server.connection import ClientConnection
from basic_web_server.exceptions import BadRequestError, RequestTimeoutError, RequestTooLargeError
from basic_web_server.response import Response

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

TEST_LOGGER = logging.getLogger("test_logger")

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert len(fake_socket.sent_data) == 2

    assert b"Response for /first" in fake_socket.sent_data[0]
    assert b"Response for /second" in fake_socket.sent_data[1]

def test_connection_timeout_stops_handling():
    fake_socket = TimeoutSocket([])

    config = ServerConfig(client_timeout=3.5)

    connection = ClientConnection(fake_socket, "fake_address", application, config, TEST_LOGGER)
    connection.handle()

    assert fake_socket.timeout == 3.5
    assert fake_socket.sent_data == []

def test_make_response_from_body_and_status():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    response = connection._make_response(("Not Found", 404))

    assert response.status_code == 404
    assert response.body == b"Not Found"
    assert response.headers == []

def test_make_response_with_dict_headers():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
        TEST_LOGGER
    )

    connection._receive_http_request()

    assert fake_socket.recv_sizes[0] == 128

def test_receive_http_request_returns_none_on_clean_eof():
    fake_socket = FakeSocket([])

    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    result = connection._receive_http_request()

    assert result is b""

def test_receive_http_request_raises_on_incomplete_request():
    raw_data = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    with pytest.raises(RequestTooLargeError) as error_info:
        connection._receive_http_request()

    assert error_info.value.close_connection is True
    assert error_info.value.status_code == 413

def test_receive_http_request_raises_when_body_exceeds_max_size():
    raw_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length:" + str(TEST_CONFIG.max_request_size + 1).encode() + b"\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([raw_data])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    with pytest.raises(RequestTooLargeError) as error_info:
        connection._receive_http_request()

    assert error_info.value.close_connection is True
    assert error_info.value.status_code == 413

def test_idle_connection_timeout_returns_empty():
    fake_socket = TimeoutSocket([])

    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    with pytest.raises(BadRequestError) as error_info:
        connection._receive_http_request()

    assert "Multiple Content-Length headers are not allowed." in str(error_info.value)
    assert error_info.value.close_connection is True

def test_make_response_from_body():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    response = connection._make_response("Hello World")

    assert response.status_code == 200
    assert response.body == b"Hello World"
    assert response.headers == []

def test_make_response_from_body_and_status():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    response = connection._make_response(("Not Found", 404))

    assert response.status_code == 404
    assert response.body == b"Not Found"
    assert response.headers == []

def test_make_response_from_body_status_and_headers():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

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
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert (
        b"GET /second HTTP/1.1" in connection.buffer
    )

def test_connection_uses_given_logger():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)  

    assert connection.logger is TEST_LOGGER

def test_make_error_response():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    response = connection._make_error_response(400, "Bad Request")

    response_data = response.to_bytes()

    assert response_data.startswith(b"HTTP/1.1 400 Bad Request\r\n")
    assert b"Content-Type: text/plain; charset=utf-8\r\n" in response_data
    assert response_data.endswith(b"400 Bad Request")

def test_make_error_response_connection_close():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    response = connection._make_error_response(413, "Content Too Large", close_connection=True)

    response_data = response.to_bytes()

    assert b"Connection: close\r\n" in response_data

def test_handle_continues_after_recoveravle_http_error():
    request_data = (
        b"INVALID REQUEST\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Connection: close\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([request_data])

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=application,
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert len(fake_socket.sent_data) == 2
    assert fake_socket.sent_data[0].startswith(b"HTTP/1.1 400 Bad Request\r\n")
    assert fake_socket.sent_data[1].startswith(b"HTTP/1.1 200 OK\r\n")

def test_handle_closes_after_fatal_http_error():
    request_data = (
        b"POST / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: invalid\r\n"
        b"\r\n"
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([request_data])

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=application,
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert len(fake_socket.sent_data) == 1
    response_data = fake_socket.sent_data[0]
    assert response_data.startswith(b"HTTP/1.1 400 Bad Request\r\n")
    assert b"Connection: close\r\n" in response_data

def invalid_application(request):
    return object()  # Return an object that is not a valid response

def test_handle_returns_500_for_application_error():
    request_data = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([request_data])

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=invalid_application,
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert len(fake_socket.sent_data) == 1
    response_data = fake_socket.sent_data[0]
    assert response_data.startswith(b"HTTP/1.1 500 Internal Server Error\r\n")

def crashing_application(request):
    raise RuntimeError("Simulated application crash")

def test_handle_returns_500_for_unhandled_application_exception():
    request_data = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([request_data])

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=crashing_application,
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert len(fake_socket.sent_data) == 1
    response_data = fake_socket.sent_data[0]
    assert response_data.startswith(b"HTTP/1.1 500 Internal Server Error\r\n")

def test_handle_continues_after_unhandled_application_exception():
    calls = 0

    def application_with_one_failure(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Simulated application failure")
        return ("OK", 200, {"Content-Type": "text/plain"})

    request_data = (
        b"GET /first HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
        b"GET /second HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Connection: close\r\n"
        b"\r\n"
    )

    fake_socket = FakeSocket([request_data])

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=application_with_one_failure,
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert len(fake_socket.sent_data) == 2
    assert fake_socket.sent_data[0].startswith(b"HTTP/1.1 500 Internal Server Error\r\n")
    assert fake_socket.sent_data[1].startswith(b"HTTP/1.1 200 OK\r\n")

class RecvErrorSocket(FakeSocket):
    def __init__(self):
        self.sent_data = []
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, size):
        raise OSError("Simulated receive error")

    def sendall(self, data):
        self.sent_data.append(data)

def test_handle_closes_on_client_connection_error():
    fake_socket = RecvErrorSocket()

    connection = ClientConnection(
        client_socket=fake_socket,
        client_address="fake_address",
        application=application,
        config=TEST_CONFIG,
        logger=TEST_LOGGER
    )

    connection.handle()

    assert fake_socket.sent_data == []

def test_send_response_returns_true_on_success():
    fake_socket = FakeSocket([])
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    response = Response(body=b"Hello", status_code=200)

    result = connection._send_response(response)

    assert result is True
    assert len(fake_socket.sent_data) == 1

class SendErrorSocket_2:
    def settimeout(self, timeout):
        pass

    def sendall(self, data):
        raise OSError("Simulated send error")

def test_send_response_returns_false_on_send_error():
    fake_socket = SendErrorSocket_2()
    connection = ClientConnection(fake_socket, "fake_address", application, TEST_CONFIG, TEST_LOGGER)

    response = Response(body=b"Hello", status_code=200)

    result = connection._send_response(response)

    assert result is False