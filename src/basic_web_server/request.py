from .http import HEADER_SEPARATOR

class Request:

    def __init__(self, raw_data):
        self.raw_data = raw_data

        header_data, separator, body_data = raw_data.partition(HEADER_SEPARATOR)

        self.body = body_data
    
        header_text = header_data.decode("utf-8")
        header_lines = header_text.splitlines()

        self.method, self.target, self.version = header_lines[0].split()

        self.headers = {}
        for line in header_lines[1:]:
            name, value = line.split(":", 1)
            self.headers[name.strip()] = value.strip()

        self.path, separator, self.query_string = self.target.partition("?")


    