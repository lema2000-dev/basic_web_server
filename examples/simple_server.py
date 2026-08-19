from basic_web_server import Response, Server

def application(request):
    print("Method:", request.method)
    print("Target:", request.target)

    return Response("<h1>Hello from our basic web server!</h1>")

server = Server(application, host="127.0.0.1", port=5000)

server.run()
