"""Single entrypoint test runner for Clipping Final Boss test suite.

Usage:
    python tests/run.py
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def get_venv_python() -> Path:
    if os.name == "nt":
        candidate = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT_DIR / ".venv" / "bin" / "python"
    if candidate.exists():
        return candidate
    return Path(sys.executable)

def main() -> int:
    py = get_venv_python()
    pytest_args = [str(py), "-m", "pytest", "-v"] + sys.argv[1:]

    print("\n" + "=" * 60)
    print("  🧪 Running Clipping Final Boss Test Suite")
    print(f"  👉 Python: {py}")
    print(f"  👉 Root:   {ROOT_DIR}")
    print("=" * 60 + "\n")

    res = subprocess.run(pytest_args, cwd=ROOT_DIR)

    print("\n" + "=" * 60)
    if res.returncode == 0:
        print("  ✅ TEST SUITE RESULT: ALL TESTS PASSED (EXIT CODE 0)")
    else:
        print(f"  ❌ TEST SUITE RESULT: TESTS FAILED (EXIT CODE {res.returncode})")
    print("=" * 60 + "\n")

    return res.returncode

if __name__ == "__main__":
    sys.exit(main())
