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
    (root / "_internal" / "old.dll").write_text("old", encoding="utf-8")
    (root / "CoffeeStock.exe").write_text("old exe", encoding="utf-8")
    (root / "coffee.db").write_text("база", encoding="utf-8")
    (root / "Продажи.xlsx").write_text("продажи", encoding="utf-8")
    (root / "Накладные").mkdir()
    staging = root / "_update" / "new"
    (staging / "_internal").mkdir(parents=True)
    (staging / "_internal" / "new.dll").write_text("new", encoding="utf-8")
    (staging / "CoffeeStock.exe").write_text("new exe", encoding="utf-8")
    started = {}
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.update(args=args, **kw))
    monkeypatch.setattr(updater, "wait_for_exit", lambda pid, timeout=60: True)
    monkeypatch.setattr(updater, "VERSION", "1.0.12")

    updater.finish_update(root, staging, 123, "1.0.12")
    assert (root / "CoffeeStock.exe").read_text(encoding="utf-8") == "new exe"
    assert (root / "_internal" / "new.dll").exists() and not (root / "_internal" / "old.dll").exists()
    assert (root / "coffee.db").read_text(encoding="utf-8") == "база" and (root / "Продажи.xlsx").exists()
    assert (root / "Накладные").is_dir()
    assert started["args"] == [str(root / "CoffeeStock.exe")]
    assert started["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert updater.finished_update(root) == "1.0.12"


def test_wait_for_exit_returns_for_missing_process():
    assert updater.wait_for_exit(999999, timeout=2)


def test_finish_update_closes_old_version_that_hangs(tmp_path, monkeypatch):
    """Старая версия не закрылась сама (завис цикл событий) — новая закрывает её и всё равно обновляет."""
    import subprocess
    import sys

    root = tmp_path / "Кофеаппарат"
    root.mkdir()
    (root / "CoffeeStock.exe").write_text("old exe", encoding="utf-8")
    staging = root / "_update" / "new"
    staging.mkdir(parents=True)
    (staging / "CoffeeStock.exe").write_text("new exe", encoding="utf-8")
    hung = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    started = {}
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.update(args=args, **kw))
    monkeypatch.setattr(updater, "EXIT_WAIT", 1)
    monkeypatch.setattr(updater, "VERSION", "1.0.15")
    try:
        updater.finish_update(root, staging, hung.pid, "1.0.15")
        assert hung.wait(timeout=10) is not None  # процесс закрыт
    finally:
        if hung.poll() is None:
            hung.kill()
    log = (root / updater.LOG_NAME).read_text(encoding="utf-8")
    assert "не закрылась сама" in log
    assert (root / "CoffeeStock.exe").read_text(encoding="utf-8") == "new exe"
    assert started["args"] == [str(root / "CoffeeStock.exe")]
    assert updater.finished_update(root) == "1.0.15"


def test_failed_update_is_reported(tmp_path):
    (tmp_path / updater.LOG_NAME).write_text("обновление до версии 1.0.15\nошибка: не удалось удалить _internal\n",
                                             encoding="utf-8")
    assert "не удалось удалить" in updater.failed_update(tmp_path)
    assert not (tmp_path / updater.LOG_NAME).exists()
    (tmp_path / updater.LOG_NAME).write_text("обновление до версии 1.0.15\nготово\n", encoding="utf-8")
    assert updater.failed_update(tmp_path) is None


def test_finished_update_message(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "VERSION", "1.0.12")
    log = tmp_path / updater.LOG_NAME
    log.write_text("обновление до версии 1.0.12\nпрограмма закрыта\nфайлы заменены\nготово\n", encoding="utf-8")
    assert updater.finished_update(tmp_path) == "1.0.12"
    assert not log.exists()
    log.write_text("обновление до версии 1.0.12\nошибка: нет доступа\n", encoding="utf-8")
    assert updater.finished_update(tmp_path) is None
