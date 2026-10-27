import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from io import BytesIO

MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".xlsx", ".pptx"}


def public_url(url):
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a public HTTP or HTTPS URL.")
    if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
        raise ValueError("URLs with credentials or custom ports are not supported.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Only public websites are supported.")
    except socket.gaierror as exc:
        raise ValueError("The website address could not be resolved.") from exc
    return urlunsplit(parsed._replace(fragment=""))


def safe_name(name):
    return re.sub(r"[^\w. -]", "_", Path(name.replace("\\", "/")).name)[:100] or "document"


def validate_upload(name, data):
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Supported files: PDF, TXT, MD, CSV, XLSX, PPTX.")
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Each file must contain data and be at most 10 MB.")
    if suffix == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
        raise ValueError("This file is not a valid PDF.")
    if suffix in {".xlsx", ".pptx"}:
        try:
            with ZipFile(BytesIO(data)) as archive:
                items = archive.infolist()
                if len(items) > 2000 or sum(i.file_size for i in items) > 40 * 1024 * 1024:
                    raise ValueError("The expanded document is too large.")
        except BadZipFile as exc:
            raise ValueError("This Office document is damaged.") from exc
    return suffix


def redact(message, key=""):
    text = str(message)
    if key:
        text = text.replace(key, "[redacted]")
    return re.sub(r"gsk_[A-Za-z0-9_-]+", "[redacted]", text)[:1200]
