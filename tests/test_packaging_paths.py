from __future__ import annotations

from pathlib import Path

import pytest

from src.config import (
    APP_ID,
    ENV_APP_ROOT,
    ENV_CONFIG_DIR,
    load_config,
    resolve_app_root,
    resolve_config_dir,
    resolve_config_path,
    resolve_example_config_path,
    save_config,
    validate_config,
)


@pytest.fixture
def clean_wlcl_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_APP_ROOT, raising=False)
    monkeypatch.delenv(ENV_CONFIG_DIR, raising=False)


def test_resolve_paths_dev_uses_cwd(
    clean_wlcl_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_app_root() is None
    assert resolve_config_dir() == tmp_path.resolve()
    assert resolve_config_path() == tmp_path.resolve() / "config.json"


def test_resolve_paths_installed_uses_xdg(
    clean_wlcl_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_root = tmp_path / "opt" / "app"
    xdg = tmp_path / "xdg-config"
    app_root.mkdir(parents=True)
    monkeypatch.setenv(ENV_APP_ROOT, str(app_root))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert resolve_app_root() == app_root.resolve()
    assert resolve_config_dir() == (xdg / APP_ID).resolve()
    assert resolve_config_path() == (xdg / APP_ID / "config.json").resolve()


def test_resolve_config_dir_env_override(
    clean_wlcl_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "custom-cfg"
    monkeypatch.setenv(ENV_CONFIG_DIR, str(cfg_dir))
    assert resolve_config_dir() == cfg_dir.resolve()
    assert resolve_config_path() == cfg_dir.resolve() / "config.json"


def test_resolve_example_prefers_app_root(
    clean_wlcl_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    example = app_root / "config.example.json"
    example.write_text('{"language": "fr"}\n', encoding="utf-8")
    monkeypatch.setenv(ENV_APP_ROOT, str(app_root))
    assert resolve_example_config_path() == example.resolve()


def test_save_config_creates_parent_dirs(
    clean_wlcl_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "nested" / "cfg"
    monkeypatch.setenv(ENV_CONFIG_DIR, str(cfg_dir))
    path = save_config(validate_config({"language": "de"}))
    assert path == cfg_dir / "config.json"
    assert path.is_file()
    loaded = load_config(path)
    assert loaded["language"] == "de"


def test_load_missing_under_xdg_returns_defaults(
    clean_wlcl_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(ENV_CONFIG_DIR, str(tmp_path / "empty"))
    cfg = load_config()
    assert cfg["language"] == validate_config({})["language"]


def test_installer_prefetches_models_without_blocking_install() -> None:
    installer = (
        Path(__file__).resolve().parent.parent / "scripts" / "install-user.sh"
    )
    script = installer.read_text(encoding="utf-8")
    assert 'cp "$ROOT/scripts/prefetch-models.py" "$APP_ROOT/scripts/"' in script
    assert 'python "$APP_ROOT/scripts/prefetch-models.py"' in script
    assert "WLCL_SKIP_MODEL_PREFETCH" in script
    # Un fallo de descarga avisa pero no aborta la instalación.
    assert 'if ! python "$APP_ROOT/scripts/prefetch-models.py"; then' in script
