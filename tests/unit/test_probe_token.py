"""Session-token handling.

The token has to be pasted into the Overwolf debug window by hand. Regenerating
it every run would mean re-pasting every run, and a stale paste fails as a
confusing "auth rejected" - so a generated token is cached and reused.
"""

from __future__ import annotations

from pubg_training_bot.config.paths import ProjectPaths
from pubg_training_bot.probe import resolve_token


def test_first_run_generates_and_caches(tmp_path) -> None:
    paths = ProjectPaths(root=tmp_path)
    token, reused = resolve_token("", paths)
    assert token
    assert reused is False
    assert (paths.data_dir / "session-token").read_text(encoding="utf-8").strip() == token


def test_second_run_reuses_the_same_token(tmp_path) -> None:
    paths = ProjectPaths(root=tmp_path)
    first, _ = resolve_token("", paths)
    second, reused = resolve_token("", paths)
    assert second == first
    assert reused is True, "the operator must not have to re-paste every run"


def test_explicit_token_wins_and_is_not_persisted(tmp_path) -> None:
    paths = ProjectPaths(root=tmp_path)
    token, reused = resolve_token("explicit-token", paths)
    assert token == "explicit-token"
    assert reused is False
    assert not (paths.data_dir / "session-token").exists(), (
        "an explicitly supplied token must not be written to disk"
    )


def test_explicit_token_does_not_clobber_the_cache(tmp_path) -> None:
    paths = ProjectPaths(root=tmp_path)
    cached, _ = resolve_token("", paths)
    resolve_token("one-off", paths)
    again, reused = resolve_token("", paths)
    assert again == cached
    assert reused is True


def test_empty_cache_file_is_regenerated(tmp_path) -> None:
    paths = ProjectPaths(root=tmp_path)
    cache = paths.data_dir / "session-token"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("   \n", encoding="utf-8")
    token, reused = resolve_token("", paths)
    assert token.strip()
    assert reused is False


def test_cached_token_is_git_ignored() -> None:
    """It is a shared secret; it must never reach the repository."""
    from pubg_training_bot.config.paths import find_repo_root

    ignore = (find_repo_root() / ".gitignore").read_text(encoding="utf-8")
    assert "data/local/session-token" in ignore or "data/local/**" in ignore
