from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
from datetime import date, datetime, timedelta
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT_DIR / "public"
IMAGES_DIR = ROOT_DIR / "images"
ENV_FILE = ROOT_DIR / ".env"


def load_env_file() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
TIME_SLOTS = ["16:00", "17:30", "19:00", "20:30", "22:00"]
EVENT_TYPES = {
    "pulm": "Pulm",
    "firmaüritus": "Firmaüritus",
    "gala": "Gala",
    "sünnipäev": "Sünnipäev",
    "avalik sündmus": "Avalik sündmus",
}
PHONE_PATTERN = re.compile(r"^[0-9+ ()-]{7,30}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "broneering@send.tammets.ee").strip()
RESEND_FROM_NAME = os.getenv("RESEND_FROM_NAME", "Marek Tammets").strip()
BOOKING_TO_EMAIL = os.getenv("BOOKING_TO_EMAIL", "marek@tammets.ee").strip()
BOOKING_BCC_EMAIL = os.getenv("BOOKING_BCC_EMAIL", "").strip()
Response = tuple[HTTPStatus, list[tuple[str, str]], bytes]
LONG_CACHE_SUFFIXES = {".css", ".js", ".jpg", ".jpeg", ".png", ".webp", ".svg"}


class DeliveryError(Exception):
    pass


def resend_is_configured() -> bool:
    return bool(RESEND_API_KEY and RESEND_FROM_EMAIL and BOOKING_TO_EMAIL)


def parse_email_list(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def serialize_availability() -> dict:
    today = date.today()
    max_date = today + timedelta(days=540)
    return {
        "timeSlots": TIME_SLOTS,
        "bookedSlots": {},
        "dateRange": {"min": today.isoformat(), "max": max_date.isoformat()},
    }


def validate_booking(payload: dict) -> tuple[dict, list[str]]:
    errors: list[str] = []

    full_name = normalize_text(payload.get("fullName"))
    email = normalize_text(payload.get("email")).lower()
    phone = normalize_text(payload.get("phone"))
    event_type = normalize_text(payload.get("eventType")).lower()
    event_date = normalize_text(payload.get("eventDate"))
    time_slot = normalize_text(payload.get("timeSlot"))
    location = normalize_text(payload.get("location"))
    guests_raw = normalize_text(payload.get("guestCount"))
    notes = normalize_text(payload.get("notes"))

    if len(full_name) < 3:
        errors.append("Lisa kontaktisiku nimi.")
    if email and not EMAIL_PATTERN.match(email):
        errors.append("Sisesta korrektne e-posti aadress.")
    if not email:
        errors.append("E-posti aadress on kohustuslik.")
    if not PHONE_PATTERN.match(phone):
        errors.append("Sisesta korrektne telefoninumber.")
    if event_type and event_type not in EVENT_TYPES:
        errors.append("Vali sündmuse tüüp.")
    if time_slot and time_slot not in TIME_SLOTS:
        errors.append("Vali sobiv algusaeg.")

    if guests_raw:
        try:
            guest_count = int(guests_raw)
        except ValueError:
            guest_count = -1
        if guest_count < 10 or guest_count > 5000:
            errors.append("Külaliste arv peab jääma vahemikku 10 kuni 5000.")
    else:
        guest_count = None

    try:
        parsed_date = datetime.strptime(event_date, "%Y-%m-%d").date()
    except ValueError:
        parsed_date = None
        errors.append("Vali korrektne kuupäev.")

    if parsed_date:
        today = date.today()
        latest = today + timedelta(days=540)
        if parsed_date < today:
            errors.append("Minevikukuupäeva ei saa valida.")
        if parsed_date > latest:
            errors.append("Päringu kuupäev saab olla kuni 18 kuud ette.")

    if len(notes) > 1200:
        errors.append("Lisainfo väli on liiga pikk.")

    normalized = {
        "fullName": full_name,
        "email": email,
        "phone": phone,
        "eventType": event_type,
        "eventDate": event_date,
        "timeSlot": time_slot,
        "location": location,
        "guestCount": guest_count,
        "notes": notes,
    }
    return normalized, errors


def build_email_subject(details: dict) -> str:
    parts = ["Uus päring tammets.ee lehelt"]
    if details["eventType"]:
        parts.append(EVENT_TYPES.get(details["eventType"], details["eventType"]))
    parts.append(details["eventDate"])
    if details["timeSlot"]:
        parts.append(details["timeSlot"])
    return " • ".join(parts)


def build_email_html(reference: str, details: dict) -> str:
    event_type = EVENT_TYPES.get(details["eventType"], details["eventType"]) if details["eventType"] else "Täpsustamata"
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    notes = escape(details["notes"]) if details["notes"] else "Puudub"
    guest_count = details["guestCount"] if details["guestCount"] is not None else "Täpsustamata"
    location = escape(details["location"]) if details["location"] else "Täpsustamata"
    time_slot = escape(details["timeSlot"]) if details["timeSlot"] else "Täpsustamata"

    return f"""
    <div style="font-family:Arial,sans-serif;color:#16191d;line-height:1.6;">
      <h1 style="margin:0 0 16px;font-size:24px;">Uus päring tammets.ee lehelt</h1>
      <p style="margin:0 0 20px;color:#5b6470;">Viide: <strong>{escape(reference)}</strong></p>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:8px 0;font-weight:700;">Nimi</td><td style="padding:8px 0;">{escape(details["fullName"])}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;">E-post</td><td style="padding:8px 0;">{escape(details["email"])}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;">Telefon</td><td style="padding:8px 0;">{escape(details["phone"])}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;">Tüüp</td><td style="padding:8px 0;">{escape(event_type)}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;">Kuupäev</td><td style="padding:8px 0;">{escape(details["eventDate"])}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;">Algusaeg</td><td style="padding:8px 0;">{time_slot}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;">Külalisi</td><td style="padding:8px 0;">{guest_count}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;">Asukoht</td><td style="padding:8px 0;">{location}</td></tr>
        <tr><td style="padding:8px 0;font-weight:700;vertical-align:top;">Lisainfo</td><td style="padding:8px 0;">{notes}</td></tr>
      </table>
      <p style="margin:24px 0 0;color:#5b6470;">Saadetud: {escape(created_at)}</p>
    </div>
    """.strip()


def build_email_text(reference: str, details: dict) -> str:
    event_type = EVENT_TYPES.get(details["eventType"], details["eventType"]) if details["eventType"] else "Täpsustamata"
    lines = [
        "Uus päring tammets.ee lehelt",
        "",
        f"Viide: {reference}",
        f"Nimi: {details['fullName']}",
        f"E-post: {details['email']}",
        f"Telefon: {details['phone']}",
        f"Tüüp: {event_type}",
        f"Kuupäev: {details['eventDate']}",
        f"Algusaeg: {details['timeSlot'] or 'Täpsustamata'}",
        f"Külalisi: {details['guestCount'] if details['guestCount'] is not None else 'Täpsustamata'}",
        f"Asukoht: {details['location'] or 'Täpsustamata'}",
        f"Lisainfo: {details['notes'] or 'Puudub'}",
    ]
    return "\n".join(lines)


def send_email_via_resend(reference: str, details: dict) -> str:
    if not resend_is_configured():
        raise DeliveryError(
            "Resend ei ole seadistatud. Lisa .env faili RESEND_API_KEY, RESEND_FROM_EMAIL ja BOOKING_TO_EMAIL."
        )

    payload = {
        "from": f"{RESEND_FROM_NAME} <{RESEND_FROM_EMAIL}>",
        "to": parse_email_list(BOOKING_TO_EMAIL),
        "subject": build_email_subject(details),
        "html": build_email_html(reference, details),
        "text": build_email_text(reference, details),
        "reply_to": details["email"],
    }
    if BOOKING_BCC_EMAIL:
        payload["bcc"] = parse_email_list(BOOKING_BCC_EMAIL)
    encoded = json.dumps(payload).encode("utf-8")

    request = Request(RESEND_API_URL, data=encoded, method="POST")
    request.add_header("Authorization", f"Bearer {RESEND_API_KEY}")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "tammets-ee-booking/1.0")
    request.add_header("Idempotency-Key", reference)

    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        error_message = f"Resend vastas staatusega {exc.code}."
        try:
            payload = json.loads(response_body)
            error_message = payload.get("message") or payload.get("error") or error_message
        except json.JSONDecodeError:
            pass
        raise DeliveryError(f"Meili saatmine ebaõnnestus: {error_message}") from exc
    except URLError as exc:
        raise DeliveryError("Resend API-ga ei saadud ühendust.") from exc

    try:
        result = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise DeliveryError("Resend tagastas vigase vastuse.") from exc

    email_id = normalize_text(result.get("id"))
    if not email_id:
        raise DeliveryError("Resend ei tagastanud meili ID-d.")

    return email_id


def json_response(payload: dict, status: HTTPStatus = HTTPStatus.OK) -> Response:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(encoded)))], encoded


def static_response(raw_path: str) -> Response:
    request_path = raw_path or "/"
    if request_path == "/":
        request_path = "/index.html"

    sanitized = request_path.lstrip("/")
    if sanitized.startswith("images/"):
        requested_file = (ROOT_DIR / sanitized).resolve()
        root_dir = IMAGES_DIR.resolve()
    else:
        requested_file = (PUBLIC_DIR / sanitized).resolve()
        root_dir = PUBLIC_DIR.resolve()

    if root_dir not in requested_file.parents and requested_file != root_dir:
        return json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    if not requested_file.exists() or not requested_file.is_file():
        return json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    mime_type = mimetypes.guess_type(requested_file.name)[0] or "application/octet-stream"
    content = requested_file.read_bytes()
    cache_control = "no-cache"
    if requested_file.suffix.lower() in LONG_CACHE_SUFFIXES:
        cache_control = "public, max-age=31536000, immutable"

    return HTTPStatus.OK, [
        ("Content-Type", mime_type),
        ("Content-Length", str(len(content))),
        ("Cache-Control", cache_control),
    ], content


def handle_post_request(path: str, raw_body: bytes) -> Response:
    if path != "/api/bookings":
        return json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    if not raw_body:
        return json_response({"error": "Request body puudub."}, status=HTTPStatus.BAD_REQUEST)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return json_response({"error": "Vigane JSON payload."}, status=HTTPStatus.BAD_REQUEST)

    normalized, errors = validate_booking(payload)
    if errors:
        return json_response({"errors": errors}, status=HTTPStatus.BAD_REQUEST)

    if not resend_is_configured():
        return json_response(
            {
                "error": "Resend ei ole seadistatud. Lisa .env faili RESEND_API_KEY, RESEND_FROM_EMAIL ja BOOKING_TO_EMAIL."
            },
            status=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    reference = f"MT-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    try:
        email_id = send_email_via_resend(reference, normalized)
    except DeliveryError as exc:
        return json_response({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)

    return json_response(
        {
            "message": "Päring saadetud. Marek saab selle e-postile ja võtab sinuga ühendust.",
            "reference": reference,
            "emailId": email_id,
        },
        status=HTTPStatus.CREATED,
    )


def handle_request(method: str, path: str, raw_body: bytes = b"") -> Response:
    if method in {"GET", "HEAD"}:
        if path == "/api/availability":
            return json_response(serialize_availability())
        return static_response(path)

    if method == "POST":
        return handle_post_request(path, raw_body)

    return json_response({"error": "Method not allowed"}, status=HTTPStatus.METHOD_NOT_ALLOWED)


class BookingHandler(BaseHTTPRequestHandler):
    server_version = "MarekTammetsServer/2.0"

    def do_GET(self) -> None:
        self.dispatch_request()

    def do_HEAD(self) -> None:
        self.dispatch_request(send_body=False)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        self.dispatch_request(raw_body)

    def dispatch_request(self, raw_body: bytes = b"", send_body: bool = True) -> None:
        parsed = urlparse(self.path)
        status, headers, body = handle_request(self.command, parsed.path, raw_body)
        self.send_response(status)
        for header_name, header_value in headers:
            self.send_header(header_name, header_value)
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def application(environ: dict, start_response) -> list[bytes]:
    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    path = str(environ.get("PATH_INFO", "/")) or "/"

    try:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        content_length = 0

    body_stream = environ.get("wsgi.input")
    raw_body = body_stream.read(content_length) if body_stream and content_length > 0 else b""
    status, headers, body = handle_request(method, path, raw_body)
    start_response(f"{status.value} {status.phrase}", headers)
    if method == "HEAD":
        return [b""]
    return [body]


wsgi_app = application


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), BookingHandler)
    print(f"Server töötab aadressil http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer peatatud.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
