import socket

from .exceptions import (
    ApplicationError,
    BadRequestError,
    ClientConnectionError,
    HTTPError,
    RequestTimeoutError,
    RequestTooLargeError,
)
from .http import HEADER_SEPARATOR
from .request import Request
from .response import Response


class ClientConnection:
    def __init__(self, client_socket, client_address, application, config, logger):
        self.socket = client_socket
        self.client_address = client_address
        self.config = config
        self.application = application
        self.logger = logger
        self.buffer = b""

        self.socket.settimeout(self.config.client_timeout)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def handle(self):
        while True:
            try:
                request_data = self._receive_http_request()

                if not request_data:
                    self.logger.info(
                        "No more data received from %s. Closing connection.",
                        self.client_address,
                    )
                    break

                request = Request(request_data)

                try:
                    result = self.application(request)
                except Exception:
                    self.logger.exception(
                        "Unhandled application exception for %s.",
                        self.client_address,
                    )
                    error_response = self._make_error_response(
                        500,
                        "Internal Server Error",
                        close_connection=False,
                    )
                    if not self._send_response(error_response):
                        break
                    continue

                response = self._make_response(result)

                if not self._send_response(response):
                    break

                connection_header = request.get_header("Connection", "").lower()
                if connection_header == "close":
                    self.logger.info(
                        "Client %s requested connection close.",
                        self.client_address,
                    )
                    break

            except ClientConnectionError as error:
                self.logger.warning(
                    "Client connection error from %s: %s. Closing connection.",
                    self.client_address,
                    error,
                )
                break

            except ApplicationError as error:
                self.logger.error(
                    "Application response error for %s: %s.",
                    self.client_address,
                    error,
                )
                error_response = self._make_error_response(
                    500,
                    "Internal Server Error",
                    close_connection=False,
                )
                if not self._send_response(error_response):
                    break

            except HTTPError as error:
                self.logger.warning(
                    "HTTP error from %s: %s %s - %s",
                    self.client_address,
                    error.status_code,
                    error.reason,
                    error,
                )

                error_response = self._make_error_response(
                    error.status_code,
                    error.reason,
                    close_connection=error.close_connection,
                )

                if not self._send_response(error_response):
                    break

                if error.close_connection:
                    break

                continue

    # ------------------------------------------------------------------
    # Request receiving and framing
    # ------------------------------------------------------------------
    def _receive_http_request(self):
        # Read until the complete HTTP header is available.
        while HEADER_SEPARATOR not in self.buffer:
            try:
                chunk = self._recv()
            except socket.timeout as error:
                if self.buffer:
                    raise RequestTimeoutError(
                        "Client timed out before completing the HTTP request.",
                        close_connection=True,
                    ) from error
                return b""

            if not chunk:
                if self.buffer:
                    raise BadRequestError(
                        "Client closed connection before completing the HTTP request.",
                        close_connection=True,
                    )
                return b""

            self.buffer += chunk

            if len(self.buffer) > self.config.max_request_size:
                raise RequestTooLargeError(
                    "HTTP request exceeds maximum allowed size.",
                    close_connection=True,
                )

        header_data, separator, body_and_rest = self.buffer.partition(
            HEADER_SEPARATOR
        )

        content_length_values = []

        try:
            header_text = header_data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BadRequestError(
                "HTTP header could not be decoded as UTF-8.",
                close_connection=True,
            ) from error

        # Content-Length determines where the current request ends in the stream.
        for line in header_text.splitlines():
            if line.lower().startswith("content-length:"):
                value = line.split(":", 1)[1].strip()
                content_length_values.append(value)

        if len(content_length_values) > 1:
            raise BadRequestError(
                "Multiple Content-Length headers are not allowed.",
                close_connection=True,
            )

        if not content_length_values:
            content_length = 0
        else:
            try:
                content_length = int(content_length_values[0])
            except ValueError as error:
                raise BadRequestError(
                    "Invalid Content-Length header value.",
                    close_connection=True,
                ) from error

            if content_length < 0:
                raise BadRequestError(
                    "Content-Length cannot be negative.",
                    close_connection=True,
                )

        request_length = len(header_data) + len(separator) + content_length
        if request_length > self.config.max_request_size:
            raise RequestTooLargeError(
                "HTTP request exceeds maximum allowed size.",
                close_connection=True,
            )

        body_length_available = len(body_and_rest)

        # Read only the remaining bytes promised by Content-Length.
        while body_length_available < content_length:
            try:
                chunk = self._recv()
            except socket.timeout as error:
                raise RequestTimeoutError(
                    "Client timed out before completing the HTTP request.",
                    close_connection=True,
                ) from error

            if not chunk:
                raise BadRequestError(
                    "Client closed connection before completing the HTTP request body.",
                    close_connection=True,
                )

            self.buffer += chunk
            header_data, separator, body_and_rest = self.buffer.partition(
                HEADER_SEPARATOR
            )
            body_length_available = len(body_and_rest)

        request_data = self.buffer[:request_length]
        self.buffer = self.buffer[request_length:]

        return request_data

    # ------------------------------------------------------------------
    # Response construction and transport
    # ------------------------------------------------------------------
    def _make_response(self, result):
        if isinstance(result, tuple):
            if len(result) == 2:
                body, status_code = result
                headers = []
            elif len(result) == 3:
                body, status_code, headers = result
            else:
                raise ApplicationError(
                    "Application must return body, (body, status_code) or "
                    "(body, status_code, headers) tuple."
                )
        else:
            body = result
            status_code = 200
            headers = []

        return Response(body=body, status_code=status_code, headers=headers)

    def _make_error_response(self, status_code, reason, close_connection=False):
        headers = [("Content-Type", "text/plain; charset=utf-8")]

        if close_connection:
            headers.append(("Connection", "close"))

        body = f"{status_code} {reason}"
        return Response(body=body, status_code=status_code, headers=headers)

    def _send_response(self, response):
        try:
            self.socket.sendall(response.to_bytes())
        except OSError as error:
            self.logger.warning(
                "Failed to send response to %s: %s. Closing connection.",
                self.client_address,
                error,
            )
            return False

        return True

    def _recv(self):
        try:
            return self.socket.recv(self.config.recv_buffer_size)
        except socket.timeout:
            raise
        except OSError as error:
            raise ClientConnectionError(f"Socket receive failed {error}") from error