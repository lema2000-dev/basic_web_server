from errno import EBADF
import threading
import time
import socket
import errno
import logging

from basic_web_server import Server

class RecoverableAcceptErrorSocket:
    def __init__(self, server):
        self.accept_calls = 0
        self.closed = False
        self.server = server

    def bind(self, address):
        pass

    def listen(self):
        pass

    def settimeout(self, timeout):
        pass

    def getsockname(self):
        return ("127.0.0.1", 5000)

    def accept(self):
        self.accept_calls += 1
        if self.accept_calls == 1:
            raise OSError(errno.ECONNABORTED, "Simulated aborted connect")
        self.server._running = False

        raise OSError(errno.EBADF, "Simulated closed socket")
    
    def close(self):
        self.closed = True

class FatalAcceptErrorSocket:
    def __init__(self):
        self.accept_calls = 0
        self.closed = False

    def bind(self, address):
        pass

    def listen(self):
        pass

    def settimeout(self, timeout):
        pass

    def getsockname(self):
        return ("127.0.0.1", 5000)

    def accept(self):
        self.accept_calls += 1
        raise OSError(errno.EBADF, "Simulated bad file descriptor")

    def close(self):
        self.closed = True

def application(request):
    return "Hello"

def test_server_stop():
    server = Server(application)
    
    server._run(host="127.0.0.1", port=0)

    time.sleep(1)
    server._stop()
    server._server_thread.join(timeout=1)

    assert not server._server_thread.is_alive()

class BindErrorSocket:
    def __init__(self):
        self.closed = False

    def bind(self, address):
        raise OSError(errno.EADDRINUSE, "Simulated address in use")

    def listen(self):
        pass

    def settimeout(self, timeout):
        pass

    def close(self):
        self.closed = True

class StartErrorThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        raise RuntimeError("Simulated thread start failure ")

class FakeClientSocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

class ClientStartErrorThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        raise RuntimeError("Simulated client thread start failure")

class ClientThreadErrorListeningSocket:
    def __init__(self, server, client_socket):
        self.server = server
        self.client_socket = client_socket
        self.accept_calls = 0
        self.closed = False

    def bind(self, address):
        pass

    def listen(self):
        pass

    def settimeout(self, timeout):
        pass

    def getsockname(self):
        return ("127.0.0.1", 5000)
    
    def accept(self):
        self.accept_calls += 1
        if self.accept_calls == 1:
            return (self.client_socket, ("127.0.0.1", 12345))

        self.server._running = False

        raise OSError(errno.EBADF, "Simulated closed socket")
    
    def close(self):
        self.closed = True

def test_finished_client_thread_is_removed():
    server = Server(application)

    worker_socket, peer_socket = socket.socketpair()

    client_address = (
        "127.0.0.1",
        12345,
    )

    client_thread = threading.Thread(
        target=server._handle_client,
        args=(
            worker_socket,
            client_address,
        ),
    )

    with server._client_threads_lock:
        server._client_threads.append(
            (
                client_thread,
                client_address,
            )
        )

    client_thread.start()

    peer_socket.close()

    client_thread.join(timeout=1)

    assert not client_thread.is_alive()

    with server._client_threads_lock:
        active_threads = [
            thread
            for thread, _ in server._client_threads
        ]

    assert client_thread not in active_threads

def test_server_waits_for_client_threads_on_shutdown():
    server = Server(application)

    worker_can_finish = threading.Event()

    def worker():
        worker_can_finish.wait()

    client_thread = threading.Thread(
        target=worker
    )

    client_address = (
        "127.0.0.1",
        12345,
    )

    with server._client_threads_lock:
        server._client_threads.append(
            (
                client_thread,
                client_address,
            )
        )

    client_thread.start()

    def release_worker_later():
        time.sleep(0.2)
        worker_can_finish.set()

    release_thread = threading.Thread(target=release_worker_later)

    release_thread.start()

    start = time.monotonic()

    with server._client_threads_lock:
        client_threads = [thread for thread, _ in server._client_threads]

    for thread in client_threads:
        thread.join()

    elapsed = time.monotonic() - start

    assert elapsed >= 0.2
    assert not client_thread.is_alive()

    release_thread.join()

def test_server_continues_after_recoverable_accept_error(monkeypatch, caplog):
    server = Server(application)

    recoverable_socket = RecoverableAcceptErrorSocket(server)

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: recoverable_socket)

    with caplog.at_level(logging.WARNING, logger="basic_web_server"):
        server._server()

    assert recoverable_socket.accept_calls == 2
    assert recoverable_socket.closed
    assert not server._running
    assert any(record.levelno == logging.WARNING and "Recoverable accept error" in record.getMessage() for record in caplog.records)

def test_server_stops_after_fatal_accept_error(monkeypatch, caplog):
    server = Server(application)

    fatal_socket = FatalAcceptErrorSocket()

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: fatal_socket)

    with caplog.at_level(logging.ERROR, logger="basic_web_server"):
        server._server()

    assert fatal_socket.accept_calls == 1
    assert fatal_socket.closed
    assert not server._running
    assert server._socket is None
    assert any(record.levelno == logging.ERROR and "Fatal accept error" in record.getMessage() for record in caplog.records)

def test_server_handles_bind_error(monkeypatch):
    server = Server(application)

    bind_error_socket = BindErrorSocket()

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: bind_error_socket)

    server._server()

    assert bind_error_socket.closed
    assert not server._running
    assert server._socket is None

def test_run_handles_server_thread_start_error(monkeypatch, caplog):
    server = Server(application)

    monkeypatch.setattr(threading, "Thread", StartErrorThread)
    with caplog.at_level(logging.ERROR, logger="basic_web_server"):
        server._run(host="127.0.0.1", port=5000)

    assert not server._running
    assert server._server_thread is None
    assert any(record.levelno == logging.ERROR and "Failed to start server thread" in record.getMessage() for record in caplog.records)

def test_server_handles_client_thread_start_error(monkeypatch, caplog):
    server = Server(application)

    fake_client_socket = FakeClientSocket()

    client_thread_error_socket = ClientThreadErrorListeningSocket(server, fake_client_socket)

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: client_thread_error_socket)
    monkeypatch.setattr(threading, "Thread", ClientStartErrorThread)

    with caplog.at_level(logging.ERROR, logger="basic_web_server"):
        server._server()

    assert fake_client_socket.closed
    assert server._client_threads == []
    assert client_thread_error_socket.accept_calls == 2
    assert client_thread_error_socket.closed
    assert not server._running
    assert any(record.levelno == logging.ERROR and "Failed to start client thread" in record.getMessage() for record in caplog.records)

def test_command_run_rejects_invalid_ip(monkeypatch):
    server = Server(application)

    inputs = iter(["invalid_ip", "0"])

    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_called = False

    def fake_run(host, port):
        nonlocal run_called
        run_called = True

    monkeypatch.setattr(server, "_run", fake_run)

    server._command_run()

    assert not run_called

def test_command_run_rejects_integer_port(monkeypatch):
    server = Server(application)

    inputs = iter(["127.0.0.1", "invalid_port"])

    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_called = False

    def fake_run(host, port):
        nonlocal run_called
        run_called = True

    monkeypatch.setattr(server, "_run", fake_run)

    server._command_run()

    assert not run_called

def test_command_run_rejects_out_of_range_port(monkeypatch):
    server = Server(application)

    inputs = iter(["127.0.0.1", "70000"])

    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_called = False

    def fake_run(host, port):
        nonlocal run_called
        run_called = True

    monkeypatch.setattr(server, "_run", fake_run)

    server._command_run()

    assert not run_called

def test_command_run_accepts_valid_input(monkeypatch):
    server = Server(application)

    inputs = iter(["127.0.0.1", "5000"])

    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    received_arguments = {}

    def fake_run(host, port):
        received_arguments["host"] = host
        received_arguments["port"] = port

    monkeypatch.setattr(server, "_run", fake_run)

    server._command_run()

    assert received_arguments == {"host": "127.0.0.1", "port": 5000}

def test_server_has_logger():
    server = Server(application)

    assert server.logger is not None

def test_server_logs_startup_error(monkeypatch, caplog):
    server = Server(application)

    def raise_socket_error(*args, **kwargs):
        raise OSError("Simulated startup failure")

    monkeypatch.setattr(socket, "socket", raise_socket_error)

    with caplog.at_level(logging.ERROR, logger="basic_web_server"):
        server._server()

    assert any(record.levelno == logging.ERROR and "Failed to start server" in record.getMessage() for record in caplog.records)
    assert "Simulated startup failure" in caplog.text
