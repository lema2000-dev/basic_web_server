# Basic Web Server

A small HTTP/1.1 web server written from scratch in Python for educational purposes.

## Purpose

The goal of this project is to understand what happens underneath higher-level Python web frameworks and production web servers. Instead of relying on an existing HTTP server implementation, the project builds the core request/response cycle directly on top of Python's TCP socket API.

The focus is therefore not on competing with production servers, but on learning and demonstrating the fundamentals of:

- TCP socket creation, binding, listening, accepting, receiving, and sending;
- HTTP/1.1 request framing and parsing;
- persistent connections and multiple requests on one TCP connection;
- request and response validation;
- multithreaded client handling;
- error classification and connection recovery;
- configurable timeouts, request limits, and logging;
- automated testing of normal and failure paths.

## Current capabilities

The current implementation can:

- create an IPv4 TCP listening socket on a configurable host and port;
- accept multiple clients and handle each connection in a separate thread;
- parse HTTP/1.1 request lines, headers, query strings, and request bodies;
- require and validate the HTTP/1.1 `Host` header;
- preserve repeated request and response headers;
- frame request bodies using `Content-Length`;
- keep a TCP connection open for subsequent requests when it is safe to do so;
- honor `Connection: close` from the client;
- convert a simple Python application return value into an HTTP response;
- accept application results in the forms `body`, `(body, status_code)`, or `(body, status_code, headers)`;
- automatically generate `Content-Length` for responses;
- return controlled HTTP error responses for malformed, timed-out, oversized, or unsupported requests;
- distinguish recoverable HTTP errors from framing errors that require the TCP connection to be closed;
- isolate application failures and return `500 Internal Server Error` without exposing the original exception to the client;
- handle common socket, server startup, `accept()`, `recv()`, `sendall()`, and thread-start failures;
- log server activity and errors to both the terminal and a configurable log file;
- validate server configuration before startup;
- provide an interactive terminal console with `help`, `status`, `clients`, `config`, `run`, `stop`, `quit`, `clear`, `logs`, and `version` commands.

The server currently includes explicit reason phrases for the status codes used internally (`200`, `201`, `400`, `404`, `408`, `413`, `500`, and `505`). Other valid status codes can still be used by an application, but no reason phrase is added unless it exists in the server's status table.

## Minimal example

```python
from basic_web_server import Server, ServerConfig


def application(request):
    return (
        "Hello from Basic Web Server!",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


config = ServerConfig()
server = Server(application, config)
server.start_console()
```

After starting the console, use the `run` command to choose the listening address and port.

The application callable receives a `Request` object containing the parsed method, target, path, query string, headers, and raw body.

## Configuration

`ServerConfig` currently exposes:

- `client_timeout` — timeout while receiving data from a connected client;
- `accept_timeout` — timeout used by the listening socket so shutdown can be checked regularly;
- `recv_buffer_size` — maximum number of bytes requested by each `recv()` call;
- `max_request_size` — maximum accepted request size;
- `log_file` — destination file for server logs;
- `log_level` — standard Python logging level used by the server.

Invalid configuration values raise `ConfigurationError` during configuration creation, before the server starts.

## Error handling

The project deliberately separates errors by responsibility.

HTTP-level errors are converted into HTTP responses. If the current request boundary is still known, the connection may remain usable. If request framing becomes unreliable—for example because of an invalid `Content-Length`, an incomplete request, or an oversized request—the server sends an error response with `Connection: close` and stops using that TCP stream.

Transport-level failures such as socket receive errors are treated differently: the connection is closed without attempting to continue HTTP communication. Application errors are logged on the server and converted into a generic `500 Internal Server Error` response.

This separation is one of the main learning goals of the project: an HTTP error, an application error, and a TCP/socket failure are not the same kind of failure and should not be handled identically.

## Intentional limitations

This project is a learning-oriented server, **not a production-ready HTTP implementation**. In its current form it does not provide, among other things:

- HTTPS/TLS;
- HTTP/2 or HTTP/3;
- HTTP/1.0 compatibility;
- chunked transfer encoding;
- streaming request or response bodies;
- compression or content negotiation;
- routing, middleware, templates, sessions, cookies, authentication, or static-file serving as framework features;
- asynchronous I/O or a configurable worker/thread pool;
- production-grade protection against slow clients, denial-of-service attacks, or all HTTP request-smuggling/framing edge cases;
- complete RFC-level HTTP syntax validation;
- graceful process management, daemonization, hot reload, or zero-downtime restarts.

For these reasons it should not be exposed as an internet-facing production server in its current state.

## Possible future development

The codebase can be extended in several directions depending on whether the project remains educational or evolves toward a more capable server. Useful next steps could include:

- more complete HTTP/1.1 compliance and header/token validation;
- support for chunked transfer encoding;
- streaming bodies and responses instead of buffering complete messages in memory;
- configurable header-size and body-size limits;
- improved connection lifecycle and graceful shutdown behavior;
- a worker pool or asynchronous architecture for higher concurrency;
- TLS support;
- richer request metadata and URL parsing;
- routing and middleware abstractions;
- static-file handling;
- more configurable logging and log rotation;
- packaging and command-line entry points for easier installation and startup;
- interoperability and fuzz testing against a wider range of HTTP clients and malformed requests.

Some of these additions would intentionally move the project closer to a framework or production server. Others—especially stricter protocol handling, streaming, concurrency experiments, and additional tests—would preserve its value as a focused study of web-server internals.

## Testing

The repository contains a pytest-based test suite covering request parsing, response construction, configuration, connection handling, server lifecycle behavior, error paths, and logging-related behavior.

Run the tests from the project root with:

```bash
pytest
```

For development dependencies:

```bash
pip install -e ".[dev]"
```

## Project status

The current version is `0.1.0`. It represents a functional educational HTTP/1.1 server with deliberate scope limitations and a strong emphasis on explicit control flow, understandable architecture, error handling, and tests.