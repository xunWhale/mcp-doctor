import json

from mcp_doctor import cli
from mcp_doctor.model import Report, Stage


def test_json_output(monkeypatch, capsys):
    class FakeRunner:
        def __init__(self, *args):
            pass
        def run(self):
            return Report("stdio", "fake", [Stage("transport", "FAIL", 1.0, "missing", "install")])
    monkeypatch.setattr(cli, "Runner", FakeRunner)
    assert cli.main(["stdio", "fake", "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["stages"][0]["advice"] == "install"


def test_text_output(monkeypatch, capsys):
    class FakeRunner:
        def __init__(self, *args):
            pass
        def run(self):
            return Report("sse", "http://localhost/sse", [Stage("transport", "PASS", 2.0, "connected")])
    monkeypatch.setattr(cli, "Runner", FakeRunner)
    assert cli.main(["sse", "http://localhost/sse"]) == 0
    assert "[PASS]" in capsys.readouterr().out
