"""Secure upload validation: extension allow-list, size limit and content signature."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from rest_framework.exceptions import ValidationError


@dataclass(frozen=True)
class FileKind:
    label: str
    extensions: tuple[str, ...]
    signatures: tuple[bytes, ...]  # empty = no binary signature check (text formats)
    max_mb: int | None = None


IMAGE = FileKind(
    "image",
    (".png", ".jpg", ".jpeg", ".webp"),
    (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF"),
    max_mb=5,
)
PDF = FileKind("PDF", (".pdf",), (b"%PDF-",))


def validate_upload(file: UploadedFile, kind: FileKind) -> None:
    name = file.name or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in kind.extensions:
        raise ValidationError(
            f"Unsupported file type '{ext or 'none'}'. Allowed {kind.label} types: {', '.join(kind.extensions)}."
        )
    limit_mb = kind.max_mb or settings.MAX_UPLOAD_SIZE_MB
    if file.size > limit_mb * 1024 * 1024:
        raise ValidationError(f"File is too large. Maximum size is {limit_mb} MB.")
    if kind.signatures:
        head = file.read(16)
        file.seek(0)
        if not any(head.startswith(sig) for sig in kind.signatures):
            raise ValidationError(f"File content does not look like a valid {kind.label}.")
        if kind is IMAGE:
            _verify_image(file)


def _verify_image(file: UploadedFile) -> None:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(file) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValidationError("The image file is corrupt or not a supported image.") from exc
    finally:
        file.seek(0)


def random_upload_path(prefix: str, filename: str) -> str:
    """Never trust client filenames for storage paths."""
    ext = os.path.splitext(filename)[1].lower()
    return f"{prefix}/{uuid.uuid4().hex}{ext}"
