import pytest

from basic_web_server.exceptions import ApplicationError
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

def test_response_rejects_invalid_body_type():
    with pytest.raises(ApplicationError) as err_info:
        Response(body={"invalid": "type"}, status_code=200)

def test_response_accepts_bytes_body():
    response = Response(body=b"binary data", status_code=200)
    assert response.body == b"binary data"

def test_response_accepts_str_body():
    response = Response(body="text data", status_code=200)
    assert response.body == b"text data"

def test_response_accepts_valid_status_code():
    response = Response(body="OK", status_code=200)
    assert response.status_code == 200

def test_response_rejects_non_integer_status_code():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code="200")

def test_response_rejects_out_of_range_status_code():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=99)

    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=600)

def test_response_serializes_unknown_status_code():
    response = Response(body="Unknown", status_code=499)
    response_data = response.to_bytes()

    assert response_data.startswith(b"HTTP/1.1 499\r\n")

def test_response_non_iterable_headers():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=123)

def test_response_rejects_invalid_header_pairs():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=[("Valid-Header", "value"), ("Invalid-Header",)])

    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=[("Valid-Header", "value"), "Not-a-pair"])

def test_response_rejects_non_string_header_name_or_value():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=[(123, "value")])

    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=[("Header-Name", 456)])

def test_response_preserves_duplicate_headers():
    response = Response(
        body="OK",
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

def test_response_rejects_newline_in_header_name():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=[("Invalid\r\nHeader", "value")])

def test_response_rejects_newline_in_header_value():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=[("Header-Name", "Invalid\r\nValue")])

def test_response_rejrcts_application_content_length_header():
    with pytest.raises(ApplicationError) as err_info:
        Response(body="OK", status_code=200, headers=[("Content-Length", "10")])

def test_response_to_bytes_is_repeatable():
    response = Response(
        body="Hello",
        headers=[
            ("Content-Type", "text/plain"),
        ],
    )

    first = response.to_bytes()
    second = response.to_bytes()

    assert first == second

    assert first.count(
        b"Content-Length:"
    ) == 1

    assert second.count(
        b"Content-Length:"
    ) == 1