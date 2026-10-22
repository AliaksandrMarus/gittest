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

    script = updater.update_script(root, staging, 4242)
    assert 'PID eq 4242' in script
    assert f'rmdir /s /q "{root / "_internal"}"' in script
    assert "coffee.db" not in script and "Накладные" not in script  # данные не трогаются
    assert script.index("robocopy") < script.index("start ")

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("readme.txt", "нет программы")
    with pytest.raises(ValueError):
        updater.prepare(bad, root)
