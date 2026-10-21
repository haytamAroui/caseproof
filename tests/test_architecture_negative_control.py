"""Regression tests for architectural import isolation (standard-library only)."""
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_architecture.py"


class ArchitectureGuardTests(unittest.TestCase):
    def test_checker_rejects_forbidden_import(self) -> None:
        script = CHECKER.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            (root / "packages" / "evidence_kernel").mkdir(parents=True)
            (root / "domains" / "finance").mkdir(parents=True)
            (root / "domains" / "disputes").mkdir(parents=True)
            (root / "scripts" / "check_architecture.py").write_text(script, encoding="utf-8")
            (root / "packages" / "evidence_kernel" / "bad.py").write_text(
                "from fastapi import FastAPI\n", encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(root / "scripts" / "check_architecture.py")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden import fastapi", result.stderr + result.stdout)

    def test_checker_accepts_stdlib_only_kernel(self) -> None:
        script = CHECKER.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            (root / "packages" / "evidence_kernel").mkdir(parents=True)
            (root / "domains" / "finance").mkdir(parents=True)
            (root / "domains" / "disputes").mkdir(parents=True)
            (root / "scripts" / "check_architecture.py").write_text(script, encoding="utf-8")
            (root / "packages" / "evidence_kernel" / "good.py").write_text(
                "from dataclasses import dataclass\n", encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(root / "scripts" / "check_architecture.py")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
