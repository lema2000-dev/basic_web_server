import socket

from .request import Request
from .response import Response
from .http import HEADER_SEPARATOR

from .exceptions import ApplicationError, BadRequestError, RequestTooLargeError, RequestTimeoutError

class ClientConnection:

    def __init__(self, client_socket, client_address, application, config):
        self.socket = client_socket
        self.client_address = client_address
        self.config = config
        self.application = application
        self.buffer = b""

        self.socket.settimeout(self.config.client_timeout)

    def handle(self):
        try:
            while True:
                request_data = self._receive_http_request()

                if not request_data:
                    print(f"No more data received. Closing connection from {self.client_address}.")
                    break

                request = Request(request_data)
                result = self.application(request)
                response = self._make_response(result)

                self.socket.sendall(response.to_bytes())

                connection_header = request.get_header("Connection", "").lower()
                if connection_header == "close":
                    print(f"Connection header is 'close'. Closing connection from {self.client_address}.")
                    break
        except socket.timeout:
            print(f"Connection from {self.client_address} timed out.")
            return

    def _receive_http_request(self):
        while HEADER_SEPARATOR not in self.buffer:
            try:
                chunk = self.socket.recv(self.config.recv_buffer_size)
            except socket.timeout as error:
                if self.buffer:
                    raise RequestTimeoutError("Client timed out before completing the HTTP request.", close_connection=True) from error
                return b""      
            
            if not chunk:
                if self.buffer:
                    raise BadRequestError("Client closed connection before completing the HTTP request.", close_connection=True)
                return b""
            self.buffer += chunk

            if len(self.buffer) > self.config.max_request_size:
                raise RequestTooLargeError("HTTP request exceeds maximum allowed size.", close_connection=True)

        header_data, separator, body_and_rest = self.buffer.partition(HEADER_SEPARATOR)

        content_length_values = []

        header_text = header_data.decode("utf-8")

        for line in header_text.splitlines():
            if line.lower().startswith("content-length:"):
                value = line.split(":", 1)[1].strip()
                content_length_values.append(value)

        if len(content_length_values) > 1:
            raise BadRequestError("Multiple Content-Length headers are not allowed.", close_connection=True)

        if not content_length_values:
            content_length = 0
        else:
            try:
                content_length = int(content_length_values[0])
            except ValueError as error:
                raise BadRequestError("Invalid Content-Length header value.", close_connection=True) from error
            if content_length < 0:
                raise BadRequestError("Content-Length cannot be negative.", close_connection=True)
                

        request_length = len(header_data) + len(separator) + content_length
        if request_length > self.config.max_request_size:
            raise RequestTooLargeError("HTTP request exceeds maximum allowed size.", close_connection=True)

        body_length_available = len(body_and_rest)

        while body_length_available < content_length:
            try:
                chunk = self.socket.recv(self.config.recv_buffer_size)
            except socket.timeout as error:
                raise RequestTimeoutError("Client timed out before completing the HTTP request.", close_connection=True) from error

            if not chunk:
                raise BadRequestError("Client closed connection before completing the HTTP request body.", close_connection=True)
            self.buffer += chunk

            header_data, separator, body_and_rest = self.buffer.partition(HEADER_SEPARATOR)
            body_length_available = len(body_and_rest)

        request_data = self.buffer[:request_length]
        self.buffer = self.buffer[request_length:]

        return request_data

    def _make_response(self, result):
        if isinstance(result, tuple):
            if len(result) == 2:
                body, status_code = result
                headers = []

            elif len(result) == 3:
                body, status_code, headers = result

            else:
                raise ApplicationError("Application must return body, (body, status_code) or (body, status_code, headers) tuple.")

        else:
            body = result
            status_code = 200
            headers = []

        return Response(body=body, status_code=status_code, headers=headers)
        

