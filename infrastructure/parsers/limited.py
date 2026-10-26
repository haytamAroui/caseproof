"""Disposable/internal Linux parser isolation with hard time/memory/output bounds."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any

from application.documents.contracts import MAX_SOURCE_BYTES
from application.extraction.contracts import ExtractionError, canonical, decode
from packages.evidence_kernel.domain.source_versions import SourceVersion


class LimitedDocumentParser:
    def __init__(self, *, timeout: int = 8) -> None:
        if type(timeout) is not int or not 1 <= timeout <= 15:
            raise ExtractionError("bounded parser timeout required")
        self.timeout = timeout
        self.identity = f"caseproof-parser-v1;pypdf={version('pypdf')};defusedxml={version('defusedxml')};python={sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def parse(self, source: SourceVersion) -> dict[str, Any]:
        if not sys.platform.startswith("linux"):
            raise ExtractionError("resource-limited Linux parser worker required")
        if not 0 < len(source.content) <= MAX_SOURCE_BYTES:
            raise ExtractionError("document byte limit")
        if source.media_type not in {
            "text/plain",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/xml",
            "text/xml",
            "message/rfc822",
        }:
            raise ExtractionError("unsupported document media type")
        # Deliberately exclude environment keys, proxy configuration and credentials.
        data = canonical(
            {"data": base64.b64encode(source.content).decode("ascii"), "media_type": source.media_type}
        ).encode()
        env = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"}
        with TemporaryFile() as output:
            try:
                run = subprocess.run(
                    [sys.executable, "-m", "infrastructure.parsers.worker"],
                    input=data,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    timeout=self.timeout,
                    cwd=Path(__file__).resolve().parents[2],
                    env=env,
                    start_new_session=True,
                    close_fds=True,
                )
            except subprocess.TimeoutExpired:
                raise ExtractionError("document_parser_timeout") from None
            output.seek(0, os.SEEK_END)
            if output.tell() > 2 * 1024 * 1024:
                raise ExtractionError("document_parser_output_limit")
            output.seek(0)
            try:
                result = decode(output.read().decode("utf-8"))
            except (ValueError, UnicodeError):
                raise ExtractionError("document_parser_failed") from None
        if run.returncode != 0 or result.get("ok") is not True or set(result) != {"ok", "artifact"}:
            raise ExtractionError("document_parse_rejected")
        artifact = result["artifact"]
        if type(artifact) is not dict:
            raise ExtractionError("document_parser_failed")
        if type(artifact.get("parser_id")) is not str:
            raise ExtractionError("document_parser_identity_invalid")
        artifact["parser_id"] = self.identity + ";engine=" + artifact["parser_id"]
        return artifact
