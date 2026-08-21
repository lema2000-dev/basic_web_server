import socket

from .request import Request
from .response import Response
from .http import HEADER_SEPARATOR

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

                connection_header = request.headers.get("Connection", "").lower()
                if connection_header == "close":
                    print(f"Connection header is 'close'. Closing connection from {self.client_address}.")
                    break
        except socket.timeout:
            print(f"Connection from {self.client_address} timed out.")
            return

    def _receive_http_request(self):
        while HEADER_SEPARATOR not in self.buffer:
            chunk = self.socket.recv(self.config.recv_buffer_size)
            if not chunk:
                return b""
            self.buffer += chunk

        header_data, separator, body_and_rest = self.buffer.partition(HEADER_SEPARATOR)

        content_length = 0
        header_text = header_data.decode("utf-8")

        for line in header_text.splitlines():
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break

        body_length_available = len(body_and_rest)

        while body_length_available < content_length:
            chunk = self.socket.recv(self.config.recv_buffer_size)
            if not chunk:
                return b""
            self.buffer += chunk

            header_data, separator, body_and_rest = self.buffer.partition(HEADER_SEPARATOR)
            body_length_available = len(body_and_rest)

        request_length = len(header_data) + len(separator) + content_length
        request_data = self.buffer[:request_length]
        self.buffer = self.buffer[request_length:]

        return request_data

    def _make_response(self, result):
        if isinstance(result, (str, bytes)):
            body = result
            status_code = 200
            headers = {}

        elif isinstance(result, tuple):
            if len(result) == 2:
                body, status_code = result
                headers = {}
            elif len(result) == 3:
                body, status_code, headers = result
            else:
                raise TypeError("Response tuple must have 2 or 3 elements: (body, status_code) or (body, status_code, headers)")

        else:
            raise TypeError("Application must return a string, bytes, or a tuple (body, status_code) or (body, status_code, headers)")

        return Response(body=body, status_code=status_code, headers=headers)
        

