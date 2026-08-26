CRLF = "\r\n"
HEADER_SEPARATOR = b"\r\n\r\n"

STATUS_REASONS = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    404: "Not Found",
    408: "Request Timeout",
    413: "Content Too Large",
    500: "Internal Server Error",
    505: "HTTP Version Not Supported",
}

