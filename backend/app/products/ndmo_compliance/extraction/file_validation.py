"""File-content validation — port of cortex ``utils/file_validation.py``.

Two intentional deviations from the original:

  1. **No HTTPException coupling.**  Cortex's validator raises FastAPI's
     HTTPException, which leaks an HTTP concept into a background workflow
     handler.  We return a structured ``ValidationResult`` dataclass
     instead; the router layer translates failures into 4xx if needed.
  2. **No ``python-magic`` dependency** in the v1 port — the magic-byte
     check on its own is enough for the file types NDMO accepts (PDF,
     Word, Excel, PowerPoint).  ``python-magic`` requires the libmagic
     system library which we'd otherwise have to add to the Docker image
     for marginal benefit.  Easy to re-enable if NDMO later admits more
     formats.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any

import pymupdf
from PIL import Image

logger = logging.getLogger(__name__)


# File-type config table — direct port of cortex's FILE_TYPES dict, trimmed
# to the formats your spec lists for NDMO ingestion: PDF / Word / Excel /
# PowerPoint.  Image upload isn't in scope but the entry is kept for
# completeness because Req PDFs sometimes have inline scans.
FILE_TYPES: dict[str, dict[str, Any]] = {
    "pdf": {
        "extensions": [".pdf"],
        "magic_bytes": [b"%PDF-"],
        "max_size": 100 * 1024 * 1024,                  # 100 MB
    },
    "image": {
        "extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"],
        "magic_bytes": [
            b"\xFF\xD8\xFF",                            # JPEG
            b"\x89PNG\r\n\x1a\n",                       # PNG
            b"GIF87a", b"GIF89a",
            b"BM",                                       # BMP
            b"RIFF",                                     # WebP
            b"II*\x00", b"MM\x00*",                     # TIFF
        ],
        "max_size": 20 * 1024 * 1024,
    },
    "document": {
        "extensions": [".doc", ".docx", ".txt", ".rtf"],
        "magic_bytes": [
            b"PK\x03\x04",                              # DOCX (ZIP-based)
            b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",        # DOC (OLE2)
            b"{\\rtf",                                  # RTF
        ],
        "max_size": 1024 * 1024 * 1024,                 # 1 GB
    },
    "powerpoint": {
        "extensions": [".ppt", ".pptx"],
        "magic_bytes": [
            b"PK\x03\x04",
            b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",
        ],
        "max_size": 100 * 1024 * 1024,
    },
    "excel": {
        "extensions": [".xls", ".xlsx", ".xlsm"],
        "magic_bytes": [
            b"PK\x03\x04",                              # XLSX (ZIP-based)
            b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",        # XLS (OLE2)
        ],
        "max_size": 100 * 1024 * 1024,
    },
}

_EXTENSION_TO_TYPE: dict[str, str] = {
    ext.lstrip("."): family
    for family, cfg in FILE_TYPES.items()
    for ext in cfg["extensions"]
}


@dataclass(slots=True)
class ValidationResult:
    """Outcome of one file-bytes validation pass."""

    valid: bool
    file_type: str | None = None
    page_count: int | None = None
    width: int | None = None
    height: int | None = None
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class FileValidator:
    """Pure-bytes validation.  Static methods — no instance state."""

    @staticmethod
    def normalize(file_extension: str) -> str | None:
        ext = file_extension.lstrip(".").lower()
        return _EXTENSION_TO_TYPE.get(ext)

    @staticmethod
    def check_size(content: bytes, family: str) -> bool:
        max_size = FILE_TYPES[family]["max_size"]
        return len(content) <= max_size

    @staticmethod
    def check_magic_bytes(content: bytes, family: str) -> bool:
        magics = FILE_TYPES[family]["magic_bytes"]
        return any(content.startswith(m) for m in magics)

    @staticmethod
    def validate(content: bytes, file_extension: str) -> ValidationResult:
        family = FileValidator.normalize(file_extension)
        if family is None:
            return ValidationResult(valid=False, error=f"Unsupported extension: {file_extension}")

        if not FileValidator.check_size(content, family):
            max_mb = FILE_TYPES[family]["max_size"] / (1024 * 1024)
            return ValidationResult(
                valid=False,
                file_type=family,
                error=f"File too large.  Max {max_mb:.0f} MB for {family}.",
            )

        if not FileValidator.check_magic_bytes(content, family):
            return ValidationResult(
                valid=False,
                file_type=family,
                error="File content doesn't match the declared extension's magic bytes.",
            )

        # Structural check per family.
        if family == "pdf":
            try:
                doc = pymupdf.open(stream=content, filetype="pdf")
                page_count = doc.page_count
                doc.close()
                return ValidationResult(valid=True, file_type=family, page_count=page_count)
            except Exception as exc:  # noqa: BLE001
                return ValidationResult(valid=False, file_type=family, error=f"Invalid PDF: {exc}")

        if family == "image":
            try:
                with Image.open(io.BytesIO(content)) as img:
                    return ValidationResult(
                        valid=True,
                        file_type=family,
                        width=img.size[0],
                        height=img.size[1],
                        extra={"format": img.format, "mode": img.mode},
                    )
            except Exception as exc:  # noqa: BLE001
                return ValidationResult(valid=False, file_type=family, error=f"Invalid image: {exc}")

        # docx/xlsx/pptx/doc/xls/ppt — magic-byte + size check is the bar for v1.
        # The downstream extraction stage will catch anything malformed.
        return ValidationResult(valid=True, file_type=family)
