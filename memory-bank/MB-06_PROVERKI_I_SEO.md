# MB-06 — Проверки и сравнение SEO

- **tools/list_assets.py:** строит карту ресурсов для каталога/страницы.
  - Запуск: `python tools/list_assets.py [пути] --output artifacts/assets.json`.
  - Отчёт группирует стили, скрипты, изображения, медиа и встроенные ресурсы, отмечает наличие локальных файлов.
- **tools/check_links.py:**
  - Аргументы: `--scope <каталог>` (по умолчанию `nlping.ru`) или `--manifest tools/url_manifest.txt`; опционально `--base https://…` для HTTP-проверок, `--include-remote` — чтобы трогать внешние URL.
  - Без `--base` проверяет только наличие локальных файлов; с `--base` дергает HEAD/GET и фиксирует статусы. Выходит с кодом `1`, если есть пропавшие файлы или ошибки статуса.
  - Лог: `logs/check_links-*.json` (содержит список документов и активов, напротив проблемы — `missing_file`/`http_error`).
- **tools/check_utf8.py:**
  - Источник URL: `tools/url_manifest.txt` (по умолчанию) или произвольные `--scope` каталоги.
  - Команда: `python tools/check_utf8.py --manifest tools/url_manifest.txt` или `python tools/check_utf8.py --scope nlping.ru/p/0`.
  - По желанию добавь `--base http://localhost:8000`, чтобы HEAD/GET-проверка фиксировала заголовок `Content-Type`.
  - Скрипт отмечает `charset`, символы `�` (и `ï¿½`/`пїЅ`), сравнивает `<title>`, `meta description`, `h1` с оффлайн-слепком (`snapshot/seo_baseline.json.gz`) и сохраняет diff в разделе `comparisons`.
  - Лог: `logs/check_utf8-*.json`, его имя вносить в дорожную карту.
- **Ручная проверка:** после каждого автоматического прогона открыть минимум 3 ключевые страницы (главная, произвольная статья, RSS).
