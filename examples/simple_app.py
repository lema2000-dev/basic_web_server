def application(request):
    print(f"Received request: {request.method} {request.target}")
    return (
        '{"status": "ok"}',
        200,
        {
            "Content-Type": "application/json",
            "X-Test": "Hello"
        },
    )