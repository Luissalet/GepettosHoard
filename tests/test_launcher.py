import io
import json

import start


def test_launcher_does_not_mistake_another_healthy_service_for_this_app(monkeypatch):
    monkeypatch.setattr(
        start.urllib.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps({"ok": True, "appOpen": True}).encode()),
    )
    assert not start.running()


def test_launcher_recognizes_its_own_service(monkeypatch):
    def response(url, **kwargs):
        assert url == "http://127.0.0.1:8767/api/health"
        return io.BytesIO(json.dumps({"ok": True, "application": "sculptors-hoard"}).encode())

    monkeypatch.setattr(start.urllib.request, "urlopen", response)
    assert start.running()
