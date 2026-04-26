from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from timetable.editor import MoveValidationError, ScheduleEditor, parse_slot_key


class TimetableRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, editor: ScheduleEditor, **kwargs) -> None:
        self.editor = editor
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/valid-slots"):
            session_id = parsed.path[len("/api/sessions/") : -len("/valid-slots")].strip("/")
            query = parse_qs(parsed.query)
            week_pattern = query.get("week_pattern", [None])[0]
            self.handle_valid_slots(session_id, week_pattern)
            return
        if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/valid-rooms"):
            session_id = parsed.path[len("/api/sessions/") : -len("/valid-rooms")].strip("/")
            query = parse_qs(parsed.query)
            week_pattern = query.get("week_pattern", [None])[0]
            slot_key = query.get("slot_key", [None])[0]
            self.handle_valid_rooms(session_id, slot_key, week_pattern)
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/move":
            self.handle_move()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unsupported API endpoint.")

    def handle_valid_slots(self, session_id: str, week_pattern: str | None) -> None:
        try:
            payload = {
                "session_id": session_id,
                "valid_slots": self.editor.get_valid_targets(session_id, week_pattern=week_pattern),
            }
            self.send_json(payload)
        except MoveValidationError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def handle_valid_rooms(
        self,
        session_id: str,
        slot_key: str | None,
        week_pattern: str | None,
    ) -> None:
        try:
            if slot_key is None:
                raise MoveValidationError("Missing slot_key.")
            slot_id = parse_slot_key(slot_key)
            payload = {
                "session_id": session_id,
                "valid_rooms": self.editor.get_valid_rooms(
                    session_id,
                    slot_id=slot_id,
                    week_pattern=week_pattern,
                ),
            }
            self.send_json(payload)
        except MoveValidationError as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def handle_move(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_payload = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
            session_id = payload["session_id"]
            slot_id = parse_slot_key(payload["slot_key"])
            week_pattern = payload.get("week_pattern")
            room_id = payload.get("room_id")
            result = self.editor.move_session(
                session_id,
                slot_id,
                week_pattern=week_pattern,
                room_id=room_id,
            )
            self.send_json({"ok": True, "move": result})
        except (KeyError, ValueError, json.JSONDecodeError, MoveValidationError) as exc:
            self.send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_output_dir(output_dir: Path, host: str = "127.0.0.1", port: int = 8050) -> None:
    editor = ScheduleEditor(output_dir)

    def handler(*args, **kwargs):
        return TimetableRequestHandler(
            *args,
            directory=str(output_dir),
            editor=editor,
            **kwargs,
        )

    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving timetable editor on http://{host}:{port}/teacher_timetables.html")
    print(f"Output directory: {output_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
