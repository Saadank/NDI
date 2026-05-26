"""ClamAV antivirus gateway.

Direct port of cortex ``gateways/antivirus_gateway.py``.  Two cosmetic
changes:

  1. Environment variable names switched to the Datarix convention
     (``CLAMAV_HOST`` / ``CLAMAV_PORT``).  The cortex names
     (``ANTIVIRUS_HOST`` / ``ANTIVIRUS_PORT``) are still accepted as a
     fallback so dev environments that already export them keep working.
  2. ``scan_bytes`` is wrapped in an ``async`` shim so callers from the
     Restate workflow don't have to ``run_in_executor`` it.  The clamd
     library is sync; we offload via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Final

import clamd

logger = logging.getLogger(__name__)


class ClamAvGateway:
    """ClamAV daemon client (instream over TCP socket)."""

    DEFAULT_HOST: Final[str] = "clamav"
    DEFAULT_PORT: Final[int] = 3310

    def __init__(self) -> None:
        host = os.environ.get("CLAMAV_HOST") or os.environ.get("ANTIVIRUS_HOST") or self.DEFAULT_HOST
        port = int(os.environ.get("CLAMAV_PORT") or os.environ.get("ANTIVIRUS_PORT") or self.DEFAULT_PORT)
        self._client = clamd.ClamdNetworkSocket(host=host, port=port)
        logger.info("ClamAvGateway wired to %s:%d", host, port)

    def scan_bytes_sync(self, data: bytes) -> tuple[bool, str | None]:
        """Return ``(is_clean, signature_or_none)``.

        ``is_clean`` is True if ClamAV says ``OK``; False if it found a
        signature or errored.
        """
        bytes_io = io.BytesIO(data)
        scan_result = self._client.instream(bytes_io)
        verdict, signature = scan_result["stream"]
        return verdict == "OK", None if verdict == "OK" else signature

    async def scan_bytes(self, data: bytes) -> tuple[bool, str | None]:
        """Async wrapper for the sync ClamAV call (uses asyncio.to_thread)."""
        return await asyncio.to_thread(self.scan_bytes_sync, data)
