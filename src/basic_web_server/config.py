from dataclasses import dataclass

@dataclass
class ServerConfig:
    client_timeout: float = 10.0  # Timeout for client connections in seconds
    accept_timeout: float = 0.5  # Timeout for accepting new connections in seconds
    recv_buffer_size: int = 4096  # Buffer size for receiving data from clients
    max_request_size: int = 1_048_576  # Maximum size of an HTTP request in bytes