import pytest


@pytest.fixture(autouse=True)
def log_file(tmp_path, monkeypatch):
    """Tests never write to the real ~/.local/share/jarvis/jarvis.log."""
    path = tmp_path / "jarvis.log"
    monkeypatch.setenv("JARVIS_LOG", str(path))
    return path
