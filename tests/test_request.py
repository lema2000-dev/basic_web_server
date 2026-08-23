from basic_web_server import Request
import pytest
from basic_web_server.exceptions import BadRequestError, HTTPVersionNotSupportedError


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

    assert request.get_header("Host") == "127.0.0.1:5000"
    assert request.get_header("Content-Type") == "text/plain"
    assert request.get_header("Content-Length") == "5"

    assert request.body == b"Hello"

def test_request_with_query_string():
    raw_request = (
        b"GET /products?category=books&page=2 HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    request = Request(raw_request)

    assert request.target == "/products?category=books&page=2"
    assert request.path == "/products"
    assert request.query_string == "category=books&page=2"

def test_request_without_query_string():
    raw_request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    request = Request(raw_request)

    assert request.target == "/products"
    assert request.path == "/products"
    assert request.query_string == ""

def test_request_raises_on_invalid_request_line():
    raw_request = (
        b"INVALID_REQUEST_LINE\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    with pytest.raises(BadRequestError):
        Request(raw_request)

def test_request_raises_on_unsupported_http_version():
    raw_request = (
        b"GET /test HTTP/2.0\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    with pytest.raises(HTTPVersionNotSupportedError) as err_info:
        Request(raw_request)

    assert err_info.value.status_code == 505

def test_request_raises_on_invalid_header_encoding():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"X-Invalid-Header: \xff\xfe\xfd\r\n"
        b"\r\n"
    )

    with pytest.raises(BadRequestError) as err_info:
        Request(raw_request)

    assert "HTTP header could not be decoded as UTF-8." in str(err_info.value)

def test_request_raises_on_invalid_header_format():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Invalid-Header-Format\r\n"
        b"\r\n"
    )

    with pytest.raises(BadRequestError) as err_info:
        Request(raw_request)

    assert "Invalid HTTP header line" in str(err_info.value)

def test_request_raises_on_missing_header_name():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b": missing-header-name\r\n"
        b"\r\n"
    )

    with pytest.raises(BadRequestError) as err_info:
        Request(raw_request)

    assert "HTTP header name is missing" in str(err_info.value)

def test_request_raises_when_host_header_is_missing():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
    )

    with pytest.raises(BadRequestError) as err_info:
        Request(raw_request)

    assert "Host header is required in HTTP/1.1 requests." in str(err_info.value)

def test_request_header_names_are_case_insensitive():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b"HOST: localhost\r\n"
        b"Content-type: text/plain\r\n"
        b"\r\n"
    )

    request = Request(raw_request)

    assert request.get_header("Host") == "localhost"
    assert request.get_header("Content-Type") == "text/plain"

def test_request_raises_on_multiple_host_headers():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Host: example.com\r\n"
        b"\r\n"
    )

    with pytest.raises(BadRequestError) as err_info:
        Request(raw_request)

    assert "Multiple Host headers are not allowed in HTTP/1.1 requests." in str(err_info.value)
    assert err_info.value.close_connection is False

def test_request_rejects_duplicate_equal_host_headers():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    with pytest.raises(BadRequestError) as err_info:
        Request(raw_request)

    assert "Multiple Host headers are not allowed in HTTP/1.1 requests." in str(err_info.value)
    assert err_info.value.close_connection is False

def test_request_preserves_duplicate_headers():
    raw_request = (
        b"GET /test HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Set-Cookie: session=abc\r\n"
        b"Set-Cookie: language=hu\r\n"
        b"\r\n"
    )

    request = Request(raw_request)

    set_cookie_headers = request.get_headers("Set-Cookie")
    assert set_cookie_headers == ["session=abc", "language=hu"]
    assert request.headers == [
        ("host", "localhost"),
        ("set-cookie", "session=abc"),
        ("set-cookie", "language=hu")
    ]

    