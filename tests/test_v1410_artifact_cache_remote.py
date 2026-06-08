from pathlib import Path
import shutil

from typer.testing import CliRunner

from openrepro.artifact_cache import add_artifact_cache
from openrepro.artifact_cache_remote import (
    configure_cache_remote,
    list_cache_remotes,
    pull_artifact_cache,
    push_artifact_cache,
    restore_artifact_cache,
)
from openrepro.cli import app
from openrepro.project_manager import init_project
from openrepro.utils import read_json

runner = CliRunner()


def _remote_project(tmp_path: Path) -> Path:
    init_project("cache_demo", base_dir=tmp_path)
    project = tmp_path / "cache_demo"
    (project / "sources" / "paper.md").write_text("# Paper\n\nRemote cache notes.\n", encoding="utf-8")
    (project / "data" / "table.csv").write_text("x,y\n1,2\n", encoding="utf-8")
    return project


def test_configure_push_pull_and_restore_local_remote(tmp_path: Path):
    project = _remote_project(tmp_path)
    add_artifact_cache(project)
    remotes = configure_cache_remote(project, name="origin", uri=".openrepro/remotes/origin", make_default=True)
    pushed = push_artifact_cache(project)
    shutil.rmtree(project / ".openrepro" / "cache" / "sha256")

    pulled = pull_artifact_cache(project, remote="origin")
    (project / "sources" / "paper.md").unlink()
    planned = restore_artifact_cache(project)
    restored = restore_artifact_cache(project, confirm=True)

    assert remotes["schema_version"] == "1.41.0"
    assert remotes["default_remote"] == "origin"
    assert pushed["copied_blob_count"] > 0
    assert (project / ".openrepro" / "remotes" / "origin" / "openrepro_cache_remote.json").exists()
    assert pulled["copied_blob_count"] > 0
    assert planned["status"] == "planned"
    assert planned["restore_action_count"] >= 1
    assert restored["status"] == "restored"
    assert (project / "sources" / "paper.md").exists()
    assert (project / "workspace" / "cache_restore_plan.json").exists()


def test_list_cache_remotes_and_unsupported_remote(tmp_path: Path):
    project = _remote_project(tmp_path)

    configure_cache_remote(project, name="archive", uri="s3://bucket/cache", remote_type="s3", make_default=True)
    remotes = list_cache_remotes(project)

    assert remotes["remote_count"] == 1
    assert remotes["remotes"][0]["supported"] is False


def test_cli_cache_remote_flow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = _remote_project(tmp_path)
    add_artifact_cache(project)

    remote_add = runner.invoke(app, ["cache", "remote-add", "cache_demo", "--name", "origin", "--uri", ".openrepro/remotes/origin", "--default"])
    remote_list = runner.invoke(app, ["cache", "remote-list", "cache_demo"])
    pushed = runner.invoke(app, ["cache", "push", "cache_demo"])
    cache_index = read_json(project / "workspace" / "artifact_cache.json")
    first_path = cache_index["entries"][0]["path"]
    (project / first_path).unlink()
    restored = runner.invoke(app, ["cache", "restore", "cache_demo", "--confirm"])

    assert remote_add.exit_code == 0, remote_add.output
    assert "Artifact cache remote configured" in remote_add.output
    assert remote_list.exit_code == 0, remote_list.output
    assert pushed.exit_code == 0, pushed.output
    assert restored.exit_code == 0, restored.output
    assert (project / first_path).exists()
    assert (project / "workspace" / "artifact_cache_push.json").exists()
