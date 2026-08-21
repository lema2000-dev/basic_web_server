from basic_web_server import Server, ServerConfig

def test_server_uses_custom_config():
    config = ServerConfig(
        client_timeout=20.0,
        accept_timeout=0.25,
        recv_buffer_size=8192,
        max_request_size=2_097_152,
    )

    server = Server(application=lambda req: "Hello", config=config)

    assert server.config is config

def test_default_server_config():
    config = ServerConfig()

    assert config.client_timeout == 10.0
    assert config.accept_timeout == 0.5
    assert config.recv_buffer_size == 4096
    assert config.max_request_size == 1_048_576

