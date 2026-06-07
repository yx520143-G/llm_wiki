from __future__ import annotations

import hashlib
import re
import unicodedata


def normalize_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.strip().split()) for line in normalized.split("\n")]
    return "\n".join(line for line in lines if line)


def content_hash(value: str | bytes) -> str:
    if isinstance(value, str):
        data = normalize_text(value).encode("utf-8")
    else:
        data = value
    return "sha256:" + hashlib.sha256(data).hexdigest()


def ascii_slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9.]+", "-", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"-+", "-", text).strip("-.")
    return text or "untitled"


def section_slug(section_number: str, title: str) -> str:
    return f"sec-{ascii_slug(section_number)}-{ascii_slug(title)}"


def object_slug(object_type: str, object_number: str, title: str) -> str:
    return f"{ascii_slug(object_type)}-{ascii_slug(object_number)}-{ascii_slug(title)}"
