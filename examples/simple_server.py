from basic_web_server import Server, ServerConfig

from simple_app import application


def main():
    config = ServerConfig(
        client_timeout=10.0,
        accept_timeout=0.5,
        recv_buffer_size=4096,
        max_request_size=1_048_576,
        log_file="basic_web_server.log",
        log_level=20,  # logging.INFO
    )

    server = Server(application, config)
    server.start_console()

if __name__ == "__main__":
    main()