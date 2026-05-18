from __future__ import annotations

from pathlib import Path

import pytest

from claude_slack_bot.core import coordinator as coordinator_mod
from claude_slack_bot.core.coordinator import ThreadCoordinator


class _Backend:
    pass


def _coord(projects_dir: Path) -> ThreadCoordinator:
    return ThreadCoordinator(_Backend(), None, projects_dir=str(projects_dir))


def test_resolve_cwd_absolute_path(tmp_path: Path) -> None:
    target = tmp_path / "work"
    target.mkdir()
    coord = _coord(tmp_path / "Projects")

    assert coord._resolve_cwd(str(target)) == target.resolve()


def test_resolve_cwd_project_folder_name_case_insensitive(tmp_path: Path) -> None:
    projects = tmp_path / "Projects"
    target = projects / "AutoResearch"
    target.mkdir(parents=True)
    coord = _coord(projects)

    assert coord._resolve_cwd("autoresearch") == target


def test_resolve_cwd_mount_phrase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_mnt = tmp_path / "mnt"
    target = fake_mnt / "amlfs-07" / "shared" / "linke"
    target.mkdir(parents=True)
    monkeypatch.setattr(coordinator_mod, "_MOUNT_ROOT_ALIASES", {"mnt": fake_mnt, "mtn": fake_mnt})
    coord = _coord(tmp_path / "Projects")

    assert coord._resolve_cwd("mnt amlfs-07 shared linke") == target.resolve()


def test_resolve_cwd_mount_phrase_tolerates_common_typos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_mnt = tmp_path / "mnt"
    target = fake_mnt / "amlfs-07" / "shared" / "linke"
    target.mkdir(parents=True)
    monkeypatch.setattr(coordinator_mod, "_MOUNT_ROOT_ALIASES", {"mnt": fake_mnt, "mtn": fake_mnt})
    coord = _coord(tmp_path / "Projects")

    assert coord._resolve_cwd("mtn amfls-007 shared linke") == target.resolve()


def test_split_cd_target_uses_longest_resolvable_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_mnt = tmp_path / "mnt"
    target = fake_mnt / "amlfs-07" / "shared" / "linke"
    target.mkdir(parents=True)
    monkeypatch.setattr(coordinator_mod, "_MOUNT_ROOT_ALIASES", {"mnt": fake_mnt, "mtn": fake_mnt})
    coord = _coord(tmp_path / "Projects")

    cd_path, remaining = coord._split_cd_target("mnt amlfs-07 shared linke start tmux session")

    assert cd_path == "mnt amlfs-07 shared linke"
    assert remaining == "start tmux session"
