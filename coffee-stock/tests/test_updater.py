import zipfile

import pytest

from coffee_stock import updater


def release(tag, asset="CoffeeStock.zip", **kw):
    return {"tag_name": tag, "body": "что нового", "draft": False, "prerelease": False,
            "assets": [{"name": asset, "browser_download_url": f"https://x/{tag}.zip", "size": 10}], **kw}


def test_versions():
    assert updater.is_newer("1.0.12", "1.0.9")
    assert not updater.is_newer("1.0.9", "1.0.12")
    assert updater.is_newer("1.0.1", "dev")


def test_pick_release_ignores_foreign_drafts_and_missing_assets():
    picked = updater.pick_release([
        release("v2.0"),  # выпуск сайта, не программы
        release("coffee-stock-v1.0.15", draft=True),
        release("coffee-stock-v1.0.14", asset="other.zip"),
        release("coffee-stock-v1.0.9"),
        release("coffee-stock-v1.0.12"),
    ])
    assert (picked.version, picked.url) == ("1.0.12", "https://x/coffee-stock-v1.0.12.zip")
    assert updater.pick_release([release("v2.0")]) is None


def test_prepare_and_script(tmp_path):
    root = tmp_path / "Кофе"
    root.mkdir()
    archive = tmp_path / "CoffeeStock.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("CoffeeStock/CoffeeStock.exe", b"exe")
        z.writestr("CoffeeStock/_internal/lib.dll", b"dll")
    staging = updater.prepare(archive, root)
    assert (staging / "CoffeeStock.exe").read_bytes() == b"exe"

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("readme.txt", "нет программы")
    with pytest.raises(ValueError):
        updater.prepare(bad, root)


def test_install_starts_new_version_with_clean_environment(tmp_path, monkeypatch):
    root = tmp_path / "Кофеаппарат"
    root.mkdir()
    archive = tmp_path / "CoffeeStock.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("CoffeeStock.exe", b"exe")
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", r"C:\old\_internal")
    monkeypatch.setenv("_MEIPASS2", r"C:\old")
    calls = {}
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: calls.update(args=args, **kw))
    updater.install(archive, root, tmp_path / "coffee.db", "1.0.12")
    assert calls["args"][0] == str(root / "_update" / "new" / "CoffeeStock.exe")
    assert calls["args"][1:] == [updater.FINISH_FLAG, str(root), str(updater.os.getpid()), "1.0.12"]
    env = calls["env"]
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert not any(k.startswith("_PYI") for k in env) and "_MEIPASS2" not in env


def test_finish_update_replaces_program_keeps_data_and_restarts(tmp_path, monkeypatch):
    root = tmp_path / "C Claude Code" / "Кофеаппарат"
    (root / "_internal").mkdir(parents=True)
    (root / "_internal" / "old.dll").write_text("old")
    (root / "CoffeeStock.exe").write_text("old exe")
    (root / "coffee.db").write_text("база")
    (root / "Продажи.xlsx").write_text("продажи")
    (root / "Накладные").mkdir()
    staging = root / "_update" / "new"
    (staging / "_internal").mkdir(parents=True)
    (staging / "_internal" / "new.dll").write_text("new")
    (staging / "CoffeeStock.exe").write_text("new exe")
    started = {}
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.update(args=args, **kw))
    monkeypatch.setattr(updater, "wait_for_exit", lambda pid, timeout=60: None)
    monkeypatch.setattr(updater, "VERSION", "1.0.12")

    updater.finish_update(root, staging, 123, "1.0.12")
    assert (root / "CoffeeStock.exe").read_text() == "new exe"
    assert (root / "_internal" / "new.dll").exists() and not (root / "_internal" / "old.dll").exists()
    assert (root / "coffee.db").read_text() == "база" and (root / "Продажи.xlsx").exists()
    assert (root / "Накладные").is_dir()
    assert started["args"] == [str(root / "CoffeeStock.exe")]
    assert started["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert updater.finished_update(root) == "1.0.12"


def test_wait_for_exit_returns_for_missing_process():
    updater.wait_for_exit(999999, timeout=2)


def test_finished_update_message(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "VERSION", "1.0.12")
    log = tmp_path / updater.LOG_NAME
    log.write_text("обновление до версии 1.0.12\nпрограмма закрыта\nфайлы заменены\nготово\n", encoding="utf-8")
    assert updater.finished_update(tmp_path) == "1.0.12"
    assert not log.exists()
    log.write_text("обновление до версии 1.0.12\nошибка: нет доступа\n", encoding="utf-8")
    assert updater.finished_update(tmp_path) is None
