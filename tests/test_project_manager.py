from pathlib import Path

from openrepro.project_manager import get_status, init_project


def test_init_creates_project(tmp_path: Path):
    result = init_project("boc_demo", base_dir=tmp_path)
    project = tmp_path / "boc_demo"

    assert result.created is True
    assert project.exists()
    assert (project / "project_config.yaml").exists()
    for name in ["sources", "workspace", "outputs", "handoff", "reports", "logs"]:
        assert (project / name).is_dir()
    assert (project / "handoff" / "PROJECT_CONTEXT.md").exists()
    assert (project / "handoff" / "AGENT_HANDOFF.md").exists()
    assert (project / "handoff" / "NEXT_STEPS.md").exists()


def test_init_does_not_overwrite_existing(tmp_path: Path):
    init_project("boc_demo", base_dir=tmp_path)
    config = tmp_path / "boc_demo" / "project_config.yaml"
    config.write_text("custom: true\n", encoding="utf-8")

    result = init_project("boc_demo", base_dir=tmp_path)

    assert result.created is False
    assert config.read_text(encoding="utf-8") == "custom: true\n"


def test_status_for_missing_project(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status = get_status("missing")
    assert status.exists is False
    assert "openrepro init missing" in status.next_step
