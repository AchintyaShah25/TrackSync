import racemodel


def test_package_imports_without_side_effects() -> None:
    """The racemodel package imports cleanly and exposes a version.

    Why: both the ETL and the API depend on this package; a broken import would take
    down both services. Milestone 2 replaces this with real model tests.
    """
    assert racemodel.__version__
