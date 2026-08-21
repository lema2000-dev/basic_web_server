import threading
import time
import socket

from basic_web_server import Server

def application(request):
    return "Hello"

def test_server_stop():
    server = Server(application)
    
    server._run(host="127.0.0.1", port=0)

    time.sleep(1)
    server._stop()
    server._server_thread.join(timeout=1)

    assert not server._server_thread.is_alive()

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

    release_thread = threading.Thread(
        target=release_worker_later
    )

    release_thread.start()

    start = time.monotonic()

    with server._client_threads_lock:
        client_threads = [
            thread
            for thread, _ in server._client_threads
        ]

    for thread in client_threads:
        thread.join()

    elapsed = time.monotonic() - start

    assert elapsed >= 0.2
    assert not client_thread.is_alive()

    release_thread.join()

