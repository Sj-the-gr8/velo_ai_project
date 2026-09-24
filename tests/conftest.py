import dataclasses

import pytest

import config


@pytest.fixture
def test_settings(tmp_path, monkeypatch):
    """Point every module that imported ``settings`` at a temporary database and files."""
    replaced = dataclasses.replace(
        config.settings,
        database_path=tmp_path / "velo.db",
        gmail_cursor_file=tmp_path / "cursor",
        agent_screenshot_dir=tmp_path / "shots",
        agent_max_steps=8,
    )
    import agent.vision_agent
    import scripts.run_pipeline_once
    for module in (config, agent.vision_agent, scripts.run_pipeline_once):
        monkeypatch.setattr(module, "settings", replaced)
    return replaced
