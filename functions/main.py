import asyncio

from firebase_functions import https_fn

from server import app as fastapi_app


@https_fn.on_request()
def api(req: https_fn.Request) -> https_fn.Response:
    path = req.path
    if path.startswith("/api/"):
        path = path[4:]
    elif path == "/api":
        path = "/"

    body = req.get_data() or b""
    request_sent = False
    response_status = 500
    response_headers = []
    response_body = bytearray()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": req.environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/", 1)[-1],
        "method": req.method,
        "scheme": req.scheme,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": req.query_string,
        "root_path": "",
        "headers": [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in req.headers.items()
        ],
        "client": (req.remote_addr or "", 0),
        "server": (req.host.split(":", 1)[0], int(req.environ.get("SERVER_PORT", "443"))),
    }

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        request_sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        nonlocal response_status, response_headers
        if message["type"] == "http.response.start":
            response_status = message["status"]
            response_headers = [
                (key.decode("latin-1"), value.decode("latin-1"))
                for key, value in message.get("headers", [])
            ]
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    asyncio.run(fastapi_app(scope, receive, send))

    return https_fn.Response(
        bytes(response_body),
        status=response_status,
        headers=response_headers,
    )
