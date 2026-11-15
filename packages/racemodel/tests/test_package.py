import subprocess
import sys

import racemodel


def test_package_imports_without_side_effects() -> None:
    """The racemodel package imports cleanly and exposes a version.

    Why: both the ETL and the API depend on this package; a broken import would take
    down both services.
    """
    assert racemodel.__version__


def test_package_stays_pure() -> None:
    """Importing racemodel pulls in no web, DB or FastF1 modules.

    Why: architecture rule 2. The API simulates with it on a small free instance, and
    the ETL fits with it; neither should drag the other's stack along.
    """
    code = (
        "import sys, racemodel; banned = ['fastapi', 'sqlalchemy', 'psycopg', 'asyncpg', "
        "'fastf1', 'pandas']; print([m for m in banned if m in sys.modules])"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"
