import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_architecture.py"


class ArchitectureGuardTests(unittest.TestCase):
    def test_current_repo_passes(self):
        result = subprocess.run([sys.executable, str(CHECKER)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_forbidden_kernel_import_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "packages" / "evidence_kernel").mkdir(parents=True)
            (root / "scripts" / "check_architecture.py").write_text(CHECKER.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "packages" / "evidence_kernel" / "bad.py").write_text("from domains.finance import reconciliation\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(root / "scripts" / "check_architecture.py")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden import", result.stderr)

    def test_forbidden_cross_domain_import_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "domains" / "finance").mkdir(parents=True)
            (root / "scripts" / "check_architecture.py").write_text(CHECKER.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "domains" / "finance" / "bad.py").write_text("import domains.disputes\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(root / "scripts" / "check_architecture.py")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden import", result.stderr)
