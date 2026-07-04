from __future__ import annotations

import cgi
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from converter import ConvertOptions, convert_image_to_pes


ROOT = Path(__file__).parent
STATIC = ROOT / "static"
HOST = "127.0.0.1"
PORT = 8000


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_file_headers(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path == "/static/app.css":
            self._send_file_headers(STATIC / "app.css", "text/css; charset=utf-8")
            return
        if path == "/static/app.js":
            self._send_file_headers(STATIC / "app.js", "application/javascript; charset=utf-8")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_file(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path == "/static/app.css":
            self._send_file(STATIC / "app.css", "text/css; charset=utf-8")
            return
        if path == "/static/app.js":
            self._send_file(STATIC / "app.js", "application/javascript; charset=utf-8")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/convert":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self._send_json({"error": "Use multipart/form-data."}, HTTPStatus.BAD_REQUEST)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )

        upload = form["artwork"] if "artwork" in form else None
        if upload is None or not getattr(upload, "filename", ""):
            self._send_json({"error": "Please upload an image."}, HTTPStatus.BAD_REQUEST)
            return

        try:
            options = ConvertOptions(
                max_width_mm=_float_field(form, "max_width_mm", 90.0),
                colors=_int_field(form, "colors", 5),
                row_spacing_mm=_float_field(form, "row_spacing_mm", 1.4),
                stitch_length_mm=_float_field(form, "stitch_length_mm", 2.6),
            )
            pes = convert_image_to_pes(upload.file.read(), upload.filename, options)
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        stem = Path(upload.filename).stem or "design"
        output_name = f"{stem[:40]}.pes"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{output_name}"')
        self.send_header("Content-Length", str(len(pes)))
        self.end_headers()
        self.wfile.write(pes)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file_headers(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _float_field(form: cgi.FieldStorage, name: str, default: float) -> float:
    if name not in form:
        return default
    return float(form.getfirst(name) or default)


def _int_field(form: cgi.FieldStorage, name: str, default: int) -> int:
    if name not in form:
        return default
    return int(form.getfirst(name) or default)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Brother PES converter running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
