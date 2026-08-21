from basic_web_server import Server, ServerConfig

from simple_app import application

server = Server(application)
server.start_console()