from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .engine import CrisisMindService
from .live_weather import (
    auto_detect_disaster_type,
    estimate_signals,
    fetch_live_weather,
    forward_geocode,
    reverse_geocode,
)
from .reporting import EmergencyPDFBuilder


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"


class CrisisMindHandler(BaseHTTPRequestHandler):
    service: CrisisMindService
    pdf_builder = EmergencyPDFBuilder()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(TEMPLATE_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self._send_json(
                {
                    "ok": True,
                    "service": "disaster-detection-ai",
                    "registry_mode": self.service.registry_mode,
                }
            )
            return
        if parsed.path == "/api/integrations":
            self._send_json(
                {
                    "mode": self.service.registry_mode,
                    "servers": self.service.integration_status(),
                    "sources": self.service.data_sources_used(),
                }
            )
            return
        if parsed.path == "/api/scenarios":
            self._send_json({"scenarios": self.service.list_scenarios()})
            return
        if parsed.path == "/api/geocode":
            self._handle_geocode(parsed)
            return
        if parsed.path == "/api/live-weather":
            self._handle_live_weather(parsed)
            return
        if parsed.path.startswith("/static/"):
            path = STATIC_DIR / parsed.path.removeprefix("/static/")
            if path.is_file():
                mime, _ = mimetypes.guess_type(path.name)
                self._serve_file(path, mime or "application/octet-stream")
                return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            payload = self._read_json()
            report = self.service.analyze(payload)
            self._send_json({"report": report.model_dump(mode="json")})
            return
        if parsed.path == "/api/report":
            payload = self._read_json()
            report = self.service.analyze(payload)
            pdf_bytes = self.pdf_builder.build_pdf(report)
            filename = f"{report.report_id.lower()}.pdf"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_geocode(self, parsed: Any) -> None:
        """GET /api/geocode?q=Japan — forward geocode a place name."""
        qs = parse_qs(parsed.query)
        query = qs.get("q", [""])[0].strip()
        if not query:
            self._send_json(
                {"error": "Missing 'q' query parameter."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        result = forward_geocode(query)
        self._send_json(result)

    def _handle_live_weather(self, parsed: Any) -> None:
        """GET /api/live-weather?lat=XX&lon=YY — fetch real weather for coordinates."""
        qs = parse_qs(parsed.query)
        try:
            lat = float(qs["lat"][0])
            lon = float(qs["lon"][0])
        except (KeyError, IndexError, ValueError):
            self._send_json(
                {"error": "Missing or invalid 'lat' and 'lon' query parameters."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        weather = fetch_live_weather(lat, lon)
        location_name = reverse_geocode(lat, lon)
        disaster_type = auto_detect_disaster_type(weather)
        signals = estimate_signals(weather)

        self._send_json(
            {
                "lat": lat,
                "lon": lon,
                "location_name": location_name,
                "disaster_type": disaster_type,
                "weather": weather,
                "signals": signals,
            }
        )

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    service: CrisisMindService | None = None,
    prefer_mcp: bool = True,
) -> ThreadingHTTPServer:
    class BoundHandler(CrisisMindHandler):
        pass

    BoundHandler.service = service or CrisisMindService(prefer_mcp=prefer_mcp)
    BoundHandler.pdf_builder = EmergencyPDFBuilder()
    return ThreadingHTTPServer((host, port), BoundHandler)


def run(host: str = "127.0.0.1", port: int = 8765, prefer_mcp: bool = True) -> None:
    server = make_server(host=host, port=port, prefer_mcp=prefer_mcp)
    print(f"Disaster Detection AI running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Disaster Detection AI local dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--local-only", action="store_true", help="Disable MCP servers and use only local adapters.")
    args = parser.parse_args()
    run(host=args.host, port=args.port, prefer_mcp=not args.local_only)


if __name__ == "__main__":
    main()
