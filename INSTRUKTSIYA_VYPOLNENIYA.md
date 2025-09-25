# Инструкция выполнения миграции nlping.ru

Этот файл поддерживает дорожную карту `DOROZHNAYA_KARTA.md`. Следуй шагам по порядку, фиксируя результаты после каждой подпартии.

> Быстрый вызов: скажи «Протокол, шаг <код этапа>», чтобы автоматически пройти цепочку Memory → Roadmap → Instruction и перейти к нужному пункту.

## 1. Базовая подготовка (этап A)

1. **Проверить наличие страхующих артефактов.**
   - `python tools/generate_md5_baseline.py` → `snapshot/baseline_md5.txt.gz` (артефакт хранится локально, в git не попадает).
   - `tar -czf snapshot/nlping_ru_snapshot.tar.gz nlping.ru` — актуализировать архив зеркала перед крупными шагами (артефакт хранить локально; в git из каталога `snapshot/` остаётся только `.gitkeep`).
   - `python tools/generate_seo_baseline.py` — обновить `snapshot/seo_baseline.json.gz` с `<title>/<meta>/<h1>` для SEO-сравнения (каталог `snapshot/` игнорируется git, файлы остаются локально).
2. **Сформировать манифест URL.**
   - Сохранить sitemap и RSS в `tools/url_manifest.txt` (один URL в строке).
3. **Создать памятки MB-01…MB-07.**
   - Для каждой заметки указать назначение, команды и контрольные вопросы.

## 2. Инструменты проверки (этап B)

1. `tools/list_assets.py` — собирает относительные ресурсы из HTML.
   - Запуск: `python tools/list_assets.py [пути] --output artifacts/assets.json` (по умолчанию сканирует `nlping.ru`).
   - Результат: `artifacts/assets.json` с категоризированными ссылками и флагами наличия файлов.
2. `tools/check_links.py` — принимает `--scope <каталог>` (по умолчанию `nlping.ru`) или `--manifest tools/url_manifest.txt`, проверяет наличие файлов и при указании `--base` выполняет HTTP-запросы.
   - Пример: `python tools/check_links.py --scope nlping.ru/index.html` (лог появится в `logs/check_links-*.json`).
   - Для smoke-теста Pages: `python tools/check_links.py --manifest tools/url_manifest.txt --base https://<project>.pages.dev`.
3. `tools/check_utf8.py` — по списку URL/файлов проверяет `charset`, отсутствие `�`, совпадение `<title>/<meta>/<h1>` со слепком.
   - Пример полного прогона: `python tools/check_utf8.py --manifest tools/url_manifest.txt` → `logs/check_utf8-*.json`.
   - Для точечной проверки партии: `python tools/check_utf8.py --scope <каталог>` (при необходимости добавь `--base http://localhost:8000`).
4. Каждый скрипт снабдить логом (`logs/*.json`) и инструкцией по запуску.

## 3. Перенос структуры (этап C)

1. Перенос выполняй партиями с помощью `git mv`.
2. После каждой партии запускай `python tools/check_links.py --scope <каталог>` и просматривай минимум 3 страницы вручную.
3. Убедись, что корневой `index.html` — настоящая главная страница. Старый HTTrack-индекс удалить или заменить редиректом.
4. После завершения убедись, что каталог `nlping.ru/` пуст (`find nlping.ru -maxdepth 1`).

## 4. Перекодировка (этап D)

1. `tools/reencode.py` должен принимать список файлов или каталог и уметь ограничивать партию (например, `--limit 150`).
2. Каждый запуск сохраняет лог `logs/reencode-<timestamp>.json` с контрольными суммами до/после.
3. После перекодировки партии:
   - `rg -n "windows-1251" <scope>` — убедиться, что строка исчезла.
   - `python tools/check_utf8.py --scope <scope>` — проверить кодировку и SEO-блоки.
   - Просмотреть 2–3 страницы из партии вручную.
4. Повторять для всех директорий до полного отсутствия `windows-1251`.

## 5. Проверки и деплой (этап E)

1. Локальные smoke-тесты: `python -m http.server`, затем `tools/check_links.py` и `tools/check_utf8.py` по `tools/url_manifest.txt`.
2. Деплой на Cloudflare Pages, выполнить `Purge Everything`.
3. Повторить проверки по `https://<project>.pages.dev/` и `https://nlping.ru/` (если домен подключен). Использовать `curl -I` с `Cache-Control: no-cache`.
4. Зафиксировать результаты в `DOROZHNAYA_KARTA.md` и README.
5. Настроить охрану: скрипт или GitHub Action, который падает, если в diff появляется `windows-1251`.

## 6. Общие правила

- Один подпункт дорожной карты = один коммит.
- После каждого коммита обновлять раздел «Журнал прогресса» в `DOROZHNAYA_KARTA.md`.
- При возникновении ошибок описывать их в журнале и корректировать план.
- Все команды запускать из корня репозитория.

Файл хранится в корне репозитория; проверить его наличие можно командой `ls INSTRUKTSIYA_VYPOLNENIYA.md`.
