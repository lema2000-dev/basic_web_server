import socket

from .request import Request
from .response import Response
from .http import HEADER_SEPARATOR

class Server:
    def __init__(self, application, host="127.0.0.1", port=5000):
        self.host = host
        self.port = port
        self.application = application

    def run(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind((self.host, self.port))
            server_socket.listen()

            print(f"Server is listening on http://{self.host}:{self.port}")

            while True:
                client_socket, client_address = server_socket.accept()
                print("Connection received from:", client_address)

                request_data = self._receive_http_request(client_socket)

                request = Request(request_data)
                response = self.application(request)

                client_socket.sendall(response.to_bytes())
                client_socket.close()
        except KeyboardInterrupt:
            print("\nServer is shutting down.")


    def _receive_http_request(self, client_socket):
        data = b""

        while HEADER_SEPARATOR not in data:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            data += chunk

        header_data, separator, body_data = data.partition(HEADER_SEPARATOR)

        content_length = 0
        header_text = header_data.decode("utf-8")

        for line in header_text.splitlines():
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break

        while len(body_data) < content_length:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            body_data += chunk

        return header_data + HEADER_SEPARATOR + body_data


        
        