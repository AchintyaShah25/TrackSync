import subprocess
import sys


def test_api_does_not_import_fastf1():
    """Importing the API app in a fresh interpreter does not pull in fastf1.

    Why: architecture rule 1. FastF1 is slow and memory-hungry, and the free API
    container cannot afford it (ruff's banned-api rule guards the source as well).
    A subprocess is used because other test suites in the same run do import fastf1.
    """
    code = "import sys, app.main; sys.exit('fastf1' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
