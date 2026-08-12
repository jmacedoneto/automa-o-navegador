import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.app.services.browserless_live import build_live_url


def test_build_live_url_rewrites_internal_browserless_host_for_public_https():
    url = build_live_url(
        devtools_frontend_url="/devtools/inspector.html?ws=0.0.0.0:3000/devtools/page/abc123",
        public_scheme="https",
        public_host="navegador.apvsiguatemi.net",
        token="secret-token",
    )

    assert (
        url
        == "https://navegador.apvsiguatemi.net/devtools/inspector.html"
        "?wss=navegador.apvsiguatemi.net/devtools/page/abc123&token=secret-token"
    )


def test_build_live_url_keeps_existing_query_string_without_token():
    url = build_live_url(
        devtools_frontend_url="/devtools/inspector.html?ws=localhost:3000/devtools/page/xyz&panel=elements",
        public_scheme="http",
        public_host="localhost:8080",
        token="",
    )

    assert (
        url
        == "http://localhost:8080/devtools/inspector.html"
        "?ws=localhost:8080/devtools/page/xyz&panel=elements"
    )
