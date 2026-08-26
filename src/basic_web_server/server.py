import socket
import threading
import errno
import ipaddress

from .config import ServerConfig
from .connection import ClientConnection
from .logger import create_logger

RECOVERABLE_ACCEPT_ERRNOS = {errno.ECONNABORTED}

class Server:
    def __init__(self, application, config=None):
        self.host = ""
        self.port = 0
        self.application = application

        if config is None:
            config = ServerConfig()

        self.config = config
        self.logger = create_logger()

        self._socket = None
        self._running = False

        self._client_threads = []
        self._client_threads_lock = threading.Lock()

        self._server_thread = None

        self._commands = {
            "help": (self._command_help, "Show available commands"),
            "status": (self._command_status, "Show server status"),
            "clients": (self._command_clients, "Show active client connections"),
            "config": (self._command_config, "Show current server configuration"),
            "run": (self._command_run, "Run the server"),
            "stop": (self._command_stop, "Stop the server gracefully"),
            "quit": (self._command_quit, "Stop the server (if running) and exit the console"),
        }

    def start_console(self):
        self._common_loop()

    def _common_loop(self):
        loop_running = True
        while loop_running:
            try:
                command = input("> ").strip().lower()
                command_data = self._commands.get(command)
                if command_data is None:
                    print(f"Unknown command: {command!r}. Type 'help' for available commands.")
                    continue

                command_function, _ = command_data
                command_function()

                if command == "quit":
                    loop_running = False
            except (KeyboardInterrupt, EOFError):
                self._stop()
                print("\nExiting server console.")
                break

    def _server(self):
        try:
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.bind((self.host, self.port))
                self._socket.listen()
                self._socket.settimeout(self.config.accept_timeout)
            except OSError as error:
                self.logger.error("Failed to start server on %s:%s: %s", self.host, self.port, error)
                return

            self._running = True
            host, port = self._socket.getsockname()
            self.logger.info("Server is listening on http://%s:%s", host, port)

            while self._running:
                try:
                    client_socket, client_address = self._socket.accept()

                except socket.timeout:
                    continue
                
                except OSError as error:
                    if not self._running:
                        break
                    if error.errno in RECOVERABLE_ACCEPT_ERRNOS:
                        self.logger.warning("Recoverable accept error: %s. Continuing to accept new connections.", error)
                        continue
                    self.logger.error("Fatal accept error: %s.", error)   
                    break

                client_thread = threading.Thread(
                    target=self._handle_client, args=(client_socket, client_address)
                )
                with self._client_threads_lock:
                    self._client_threads.append((client_thread, client_address))
                
                try:
                    client_thread.start()
                except RuntimeError as error:
                    self.logger.error("Failed to start client thread for %s: %s", client_address, error)
                    with self._client_threads_lock:
                        self._client_threads = [
                            (t, addr) for t, addr in self._client_threads if t is not client_thread
                        ]
                    client_socket.close()
                    continue

        finally:
            self._running = False
            if self._socket is not None:
                self._socket.close()
                self._socket = None

            with self._client_threads_lock:
                client_threads_copy = [t for t, _ in self._client_threads]

            for client_thread in client_threads_copy:
                client_thread.join()

            self.logger.info("Server stopped.")

    def _run(self, host="127.0.0.1", port=0):
        self.host = host
        self.port = port
        self._server_thread = threading.Thread(target=self._server, name="server-thread")
        try:
            self._server_thread.start()
        except RuntimeError as error:
            self.logger.error("Failed to start server thread: %s", error)
            self._server_thread = None

    def _stop(self):
        self._running = False
        if self._socket is not None:
            self._socket.close()

    def _handle_client(self, client_socket, client_address):
        try:
            with client_socket:
                connection = ClientConnection(client_socket, client_address, self.application, self.config, self.logger)
                connection.handle()
        finally:
            current_thread = threading.current_thread()

            with self._client_threads_lock:
                self._client_threads = [(t, addr) for t, addr in self._client_threads if t is not current_thread]

    def _command_help(self):
        print("Available commands:")
        for name, (_, description) in self._commands.items():
            print(f"  {name:<10} {description}")

    def _command_status(self):
        if self._socket is not None:
            host, port = self._socket.getsockname()
        else:
            host, port = self.host, self.port

        with self._client_threads_lock:
            active_clients = len(self._client_threads)

        print("Server status:")
        print(f"  Running: {self._running}")
        print(f"  Address: {host}:{port}")
        print(f"  Active clients: {active_clients}")

    def _command_config(self):
        print("Server configuration:")
        print(f"  Client timeout: {self.config.client_timeout} seconds")
        print(f"  Accept timeout: {self.config.accept_timeout} seconds")
        print(f"  Receive buffer size: {self.config.recv_buffer_size} bytes")
        print(f"  Max request size: {self.config.max_request_size} bytes")

    def _command_clients(self):
        with self._client_threads_lock:
            client_threads = list(
                self._client_threads
            )

        if not client_threads:
            print("No active client connections.")
            return

        print(
            f"Active client connections: "
            f"{len(client_threads)}"
        )

        for client_thread, client_address in client_threads:
            host, port = client_address
            print(
                f"  {host}:{port} - "
                f"  {client_thread.name} "
                f"(alive={client_thread.is_alive()})"
            )

    def _command_run(self):
        if self._server_thread is not None and self._server_thread.is_alive():
            print("Server is already running.")
            return
        
        host = input("Enter host (default: 127.0.0.1): ") or "127.0.0.1"
        try:
            ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:
            print(f'Invalid IPv4 address: {host!r}. Please enter a valid IPv4 address.')
            return

        port = input("Enter port (default: 0): ") or "0"

        try:
            port = int(port)
        except ValueError:
            print("Invalid port. Port must be an integer between 0 and 65535.")
            return
        if not (0 <= port <= 65535):
            print("Invalid port. Port must be between 0 and 65535.")
            return

        self._run(host=host, port=port)

    def _command_stop(self):
        if not self._running:
            print("Server is not running.")
            return
        print("Stopping the server...")
        self._stop()

    def _command_quit(self):
        self._stop()
        print("Exiting server console.")
        