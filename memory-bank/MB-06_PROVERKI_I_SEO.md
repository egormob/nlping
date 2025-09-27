# MB-06 — Проверки и сравнение SEO

- **tools/list_assets.py:** строит карту ресурсов для каталога/страницы.  
  - Запуск: `python tools/list_assets.py [пути] --output artifacts/assets.json`.  
  - Отчёт группирует стили, скрипты, изображения, медиа и встроенные ресурсы, отмечает наличие локальных файлов.

- **tools/check_links.py:**  
  - Аргументы: `--scope <каталог>` (по умолчанию `nlping.ru`) или `--manifest tools/url_manifest.txt`; опционально `--base https://…` для HTTP-проверок, `--include-remote` — чтобы трогать внешние URL.  
  - Без `--base` проверяет только наличие локальных файлов; с `--base` дергает HEAD/GET и фиксирует статусы. Выходит с кодом `1`, если есть пропавшие файлы или ошибки статуса.  
  - Лог: `logs/check_links-*.json` (список документов/активов, напротив проблемы — `missing_file`/`http_error`).

- **tools/check_utf8.py:**  
  - Источник целей: по умолчанию `tools/url_manifest.txt` (`--manifest`), либо конкретные каталоги/файлы через `--scope`. Можно временно отключить manifest ключом `--no-manifest`.  
  - Для HTTP-проверок добавь `--base https://<project>.pages.dev`; внешние домены по умолчанию пропускаются, поэтому при необходимости укажи `--include-remote` (и при нестандартном корневом каталоге — `--primary-host example.com`).  
  - Проверяет заголовок `Content-Type` (charset), наличие `�`/`ï¿½`/`пїЅ` и типичных артефактов двойного кодирования, сопоставляет `<title>`, `meta description`, `h1` с оффлайн-слепком (`snapshot/seo_baseline.json.gz`).  
  - Примеры:
    - `python tools/check_utf8.py --manifest tools/url_manifest.txt --base https://<project>.pages.dev`
    - `python tools/check_utf8.py --scope nlping.ru/p/0 --include-remote --compact`
  - Лог: `logs/check_utf8-*.json` (differences в разделе `comparisons`). Код выхода `1` при проблемах (`missing_file`, `content_type_mismatch`, `replacement_chars` или любых `seo_mismatch:*`).

- **Ручная проверка:** после каждого автоматического прогона открыть минимум 3 ключевые страницы (главная, произвольная статья, RSS).

- **Если сессия оборвалась:** дай команду «Протокол, шаг B3» (или другой этап) и повтори последние проверки по журналу, чтобы не пропустить шаг.
