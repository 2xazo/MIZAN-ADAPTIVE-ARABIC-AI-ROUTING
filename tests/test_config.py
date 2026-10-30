"""prices() must return values that can be written to results.json."""
import json

from mizan import config


def test_verified_on_is_json_serializable(tmp_path, monkeypatch):
    (tmp_path / "prices.yaml").write_text("verified: true\nverified_on: 2026-10-30\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    assert json.loads(json.dumps(config.prices()))["verified_on"] == "2026-10-30"


def test_verified_on_null_stays_null(tmp_path, monkeypatch):
    (tmp_path / "prices.yaml").write_text("verified: false\nverified_on: null\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    assert config.prices()["verified_on"] is None
