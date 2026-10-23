"""Regression tests for the actual architectural dependency guard."""
from scripts.check_architecture import RULES, scan_source


def test_kernel_rejects_infrastructure_and_domain_imports() -> None:
    banned = RULES["packages/evidence_kernel"]
    for statement in (
        "import fastapi",
        "from sqlalchemy.orm import Session",
        "import infrastructure.persistence",
        "from domains.finance import reconciliation",
        "from application import decisions",
        "from apps.api import main",
        "__import__('supabase.client')",
        "importlib.import_module('redis.asyncio')",
    ):
        assert scan_source(statement, filename="kernel.py", banned=banned), statement


def test_application_rejects_frameworks_and_adapters() -> None:
    banned = RULES["application"]
    for statement in (
        "from fastapi import Depends",
        "import infrastructure.storage",
        "from apps.api import main",
        "from sqlalchemy import select",
    ):
        assert scan_source(statement, filename="use_case.py", banned=banned), statement


def test_domain_modules_cannot_import_other_sectors() -> None:
    assert scan_source(
        "from domains.disputes import policy",
        filename="finance.py",
        banned=RULES["domains/finance"],
    )


def test_pure_dependencies_and_standard_library_are_allowed() -> None:
    assert not scan_source(
        "from dataclasses import dataclass\nfrom packages.evidence_kernel.domain import grounding",
        filename="use_case.py",
        banned=RULES["application"],
    )
    assert not scan_source(
        "from decimal import Decimal",
        filename="finance.py",
        banned=RULES["domains/finance"],
    )


def test_nonliteral_dynamic_import_is_flagged() -> None:
    assert scan_source(
        "__import__(name)",
        filename="kernel.py",
        banned=RULES["packages/evidence_kernel"],
    )


def test_bad_python_is_reported() -> None:
    assert scan_source(
        "def broken(",
        filename="kernel.py",
        banned=RULES["packages/evidence_kernel"],
    )
