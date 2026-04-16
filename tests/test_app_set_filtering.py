import app as app_module


def test_get_available_fighters_supports_multi_set_fighters(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "FIGHTERS_DATA",
        [
            {"id": "single", "set": "Set A", "themes": []},
            {"id": "multi", "set": ["Set A", "Set B"], "themes": []},
            {"id": "other", "set": "Set C", "themes": []},
        ],
    )

    result = app_module.get_available_fighters(["Set B"])
    assert [fighter["id"] for fighter in result] == ["multi"]


def test_get_available_fighters_applies_theme_filter_with_multi_set(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "FIGHTERS_DATA",
        [
            {"id": "single", "set": "Set A", "themes": ["legend"]},
            {"id": "multi", "set": ["Set A", "Set B"], "themes": ["superhero"]},
        ],
    )

    result = app_module.get_available_fighters(["Set B"], theme_filter=["legend"])
    assert result == []
