import re


def build_live_url(
    devtools_frontend_url: str,
    public_scheme: str,
    public_host: str,
    token: str = "",
) -> str:
    if not devtools_frontend_url.startswith("/"):
        devtools_frontend_url = f"/{devtools_frontend_url}"

    # wss/ws vem do proxy reverso para conexões WebSocket — normaliza para https/http
    if public_scheme == "wss":
        public_scheme = "https"
    elif public_scheme == "ws":
        public_scheme = "http"

    ws_param = "wss" if public_scheme == "https" else "ws"

    live_path = devtools_frontend_url
    live_path = re.sub(r"ws=0\.0\.0\.0:\d+", f"{ws_param}={public_host}", live_path)
    live_path = re.sub(r"ws=localhost:\d+", f"{ws_param}={public_host}", live_path)
    live_path = re.sub(r"ws=[^&]+:\d+", f"{ws_param}={public_host}", live_path)
    live_path = re.sub(r"wss=0\.0\.0\.0:\d+", f"{ws_param}={public_host}", live_path)
    live_path = re.sub(r"wss=localhost:\d+", f"{ws_param}={public_host}", live_path)
    live_path = re.sub(r"wss=[^&]+:\d+", f"{ws_param}={public_host}", live_path)

    live_url = f"{public_scheme}://{public_host}{live_path}"
    if token:
        live_url = f"{live_url}&token={token}" if "?" in live_url else f"{live_url}?token={token}"
    return live_url
