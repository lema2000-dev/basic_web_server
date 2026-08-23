from .http import HEADER_SEPARATOR
from .exceptions import BadRequestError, HTTPVersionNotSupportedError

class Request:

    def __init__(self, raw_data):
        self.raw_data = raw_data

        header_data, separator, body_data = raw_data.partition(HEADER_SEPARATOR)

        self.body = body_data

        try:
            header_text = header_data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BadRequestError("HTTP header could not be decoded as UTF-8.")

        header_lines = header_text.splitlines()

        if not header_lines:
            raise BadRequestError("HTTP request line is missing.")

        request_line = header_lines[0]
        parts = request_line.split()

        if len(parts) != 3:
            raise BadRequestError("Invalid HTTP request line.")

        method, target, version = parts

        if not method:
            raise BadRequestError("HTTP method is missing.")

        if not target:
            raise BadRequestError("HTTP request target is missing.")

        if version != "HTTP/1.1":
            raise HTTPVersionNotSupportedError(f"Unsupported HTTP version: {version}")

        self.method = method
        self.target = target
        self.version = version

        self.path, separator, self.query_string = target.partition("?")

        host_count = 0
        self.headers = []

        for line in header_lines[1:]:
            if ":" not in line:
                raise BadRequestError(f"Invalid HTTP header line: {line}")

            name, value = line.split(":", 1)
            name = name.strip()
            value = value.strip()

            if not name:
                raise BadRequestError(f"HTTP header name is missing in line: {line}")

            if name.lower() == "host":
                host_count += 1

            self.headers.append((name.lower(), value))

        if host_count == 0:
            raise BadRequestError("Host header is required in HTTP/1.1 requests.") 

        if host_count > 1:
            raise BadRequestError("Multiple Host headers are not allowed in HTTP/1.1 requests.")

    def get_header(self, name, default=None):
        normalized_name = name.lower()

        for header_name, header_value in self.headers:
            if header_name == normalized_name:
                return header_value

        return default

    def get_headers(self, name):
        normalized_name = name.lower()

        return [value for header_name, value in self.headers if header_name == normalized_name]

         

        

        


    