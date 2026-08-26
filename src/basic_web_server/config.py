import logging
from dataclasses import dataclass

from .exceptions import ConfigurationError


@dataclass
class ServerConfig:
    # Connection and request limits.
    client_timeout: float = 10.0
    accept_timeout: float = 0.5
    recv_buffer_size: int = 4096
    max_request_size: int = 1_048_576

    # Logging settings.
    log_file: str = "basic_web_server.log"
    log_level: int = logging.INFO

    def __post_init__(self):
        valid_log_levels = {
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        }

        if (
            not isinstance(self.client_timeout, (int, float))
            or isinstance(self.client_timeout, bool)
            or self.client_timeout <= 0
        ):
            raise ConfigurationError("client_timeout must be a positive number.")

        if (
            not isinstance(self.accept_timeout, (int, float))
            or isinstance(self.accept_timeout, bool)
            or self.accept_timeout <= 0
        ):
            raise ConfigurationError("accept_timeout must be a positive number.")

        if (
            not isinstance(self.recv_buffer_size, int)
            or isinstance(self.recv_buffer_size, bool)
            or self.recv_buffer_size <= 0
        ):
            raise ConfigurationError("recv_buffer_size must be a positive integer.")

        if (
            not isinstance(self.max_request_size, int)
            or isinstance(self.max_request_size, bool)
            or self.max_request_size <= 0
        ):
            raise ConfigurationError("max_request_size must be a positive integer.")

        if not isinstance(self.log_file, str) or not self.log_file:
            raise ConfigurationError("log_file must be a non-empty string.")

        if isinstance(self.log_level, bool) or self.log_level not in valid_log_levels:
            raise ConfigurationError(
                "log_level must be one of: logging.DEBUG, logging.INFO, "
                "logging.WARNING, logging.ERROR, logging.CRITICAL."
            )