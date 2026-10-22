# Сборка под Windows со встроенным Tesseract и автообновлением

## Сборка (GitHub Actions, windows-latest)

Рабочий workflow из CoffeeStock (`.github/workflows/coffee-stock.yml`). Для новой программы замени имя, папку и префикс тега:

```yaml
on:
  push:
    paths: ["myapp/**", ".github/workflows/myapp.yml"]
  workflow_dispatch:
permissions:
  contents: write            # чтобы создавать Release
jobs:
  build:
    runs-on: windows-latest
    defaults: { run: { working-directory: myapp } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip, cache-dependency-path: "myapp/requirements*.txt" }
      - name: Tesseract с русским языком
        run: |
          choco install tesseract -y --no-progress
          $tess = "C:\Program Files\Tesseract-OCR"
          Invoke-WebRequest "https://github.com/tesseract-ocr/tessdata/raw/main/rus.traineddata" -OutFile "$tess\tessdata\rus.traineddata"
          & "$tess\tesseract.exe" --list-langs
      - run: pip install -r requirements-dev.txt
      - run: python -m pytest -q -rs
      - name: Номер версии
        run: |
          $version = "1.0.${{ github.run_number }}"
          "VERSION = `"$version`"" | Out-File -Encoding utf8 myapp\_version.py
          "VERSION=$version" | Out-File -Append -Encoding utf8 $env:GITHUB_ENV
      - name: Сборка
        run: |
          pyinstaller --noconfirm --onedir --windowed --name MyApp --collect-data pdfminer run.py
          Copy-Item -Recurse "C:\Program Files\Tesseract-OCR" dist\MyApp\tesseract
          Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist\MyApp\tesseract\doc
      - run: Compress-Archive -Path dist\MyApp\* -DestinationPath dist\MyApp.zip
      - name: Release
        env: { GH_TOKEN: "${{ github.token }}" }
        run: gh release create "myapp-v$env:VERSION" dist\MyApp.zip --title "MyApp $env:VERSION" --notes "..." --target "$env:GITHUB_SHA"
```

- `--onedir`, а не `--onefile`: onefile распаковывается во временную папку при каждом запуске (медленно), и его нельзя обновить заменой файлов.
- `--collect-data pdfminer` нужен pdfplumber'у: без этих файлов собранная программа падает на PDF.
- Tesseract копируется в `dist\MyApp\tesseract`, и `ocr.find_tesseract()` находит его рядом с exe. `TESSDATA_PREFIX` выставляется в `ocr._run`.
- Полезная проверка в CI: собранная программа видит свой Tesseract — `sys.frozen=True; sys.executable=r'dist\MyApp\MyApp.exe'; assert 'MyApp' in str(ocr.find_tesseract())`.

## Грабли Windows

- **Кодировка.** На английском Windows-сервере кодировка по умолчанию cp1252. `Path.write_text("кириллица")` без `encoding="utf-8"` падает с UnicodeEncodeError, в том числе в тестах. Указывай `encoding="utf-8"` везде, `print` в консоль — через `sys.stdout.reconfigure(encoding="utf-8")`.
- **bat-скрипты с кириллицей в путях** ломаются (кодовая страница `oem`). Обновление делай средствами Python, не через .bat.
- **Запуск exe из exe (PyInstaller).** Дочерний процесс наследует `_PYI_*` и `_MEIPASS2` и не стартует. Передавай окружение без них и с `PYINSTALLER_RESET_ENVIRONMENT=1`; флаги `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`.
- **Файлы заняты** ещё пару секунд после выхода программы: удаление делай с повторами.
- `subprocess` для tesseract — с `CREATE_NO_WINDOW`, иначе мигает консоль.
- Конвейер `pytest | tail` в bash прячет код ошибки: используй `set -e` и не пушь, пока тесты не зелёные.

## Автообновление без переустановки (как в CoffeeStock, `updater.py`)

1. Программа читает `https://api.github.com/repos/OWNER/REPO/releases`, выбирает самый новый тег с префиксом программы и архивом `MyApp.zip`, сравнивает версии.
2. Скачивает архив, распаковывает в `_update\new` и делает резервную копию базы.
3. Запускает **новую** версию с ключом `--finish-update <папка> <pid> <версия>` (с очищенным окружением, см. выше) и закрывается.
4. Новая версия ждёт выхода старой (`OpenProcess + WaitForSingleObject`), удаляет старые `MyApp.exe`, `_internal`, `tesseract`, копирует себя на их место, запускает программу из обычной папки и пишет шаги в `Обновление.log` (UTF-8).
5. Обычный запуск видит лог с «готово», показывает «Программа обновлена до версии X» и удаляет `_update`.

Данные (база, папка «Накладные», Excel-файлы) лежат рядом с exe и обновлением не трогаются.
