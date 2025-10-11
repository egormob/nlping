# MB-07 — Деплой и охрана

- **Cloudflare Pages:**
  - Деплой инициируется пушем в `work` (или main) — проверяй статус в панели.
  - После деплоя всегда выполняй `Purge Everything`.
- **Smoke-тест после деплоя:**
  - `python tools/check_links.py --manifest tools/url_manifest.txt --base https://<project>.pages.dev`.
  - `python tools/check_utf8.py --manifest tools/url_manifest.txt --base https://<project>.pages.dev`.
  - Если требуется передать проверки другому окружению, используй подготовленный список `cloudflare_request_plan.jsonl` (генерится флагами `--request-plan` и `--request-plan-format jsonl`).
  - Повторить для `https://nlping.ru` (когда домен подключён).
  - При отсутствии сетевого доступа в текущем контейнере зафиксируй правило удалённых проверок: сформируй единый промпт для внешнего агента с ссылкой `https://248c2942.nlping.pages.dev`, командами `python tools/check_links.py --manifest tools/url_manifest.txt --base … --request-plan cloudflare_request_plan.jsonl --request-plan-format jsonl --output logs/check_links-remote-<timestamp>.json`, `python tools/check_utf8.py --manifest tools/url_manifest.txt --base … --output logs/check_utf8-remote-<timestamp>.json`, `python scripts/qa_site_check.py > reports/<timestamp>_pages_remote_check.md` и просьбой завершить `cat reports/<timestamp>_pages_remote_check.md`.
- **Мониторинг:** завести cron/CI-скрипт, который раз в сутки прогоняет `tools/check_utf8.py` и сигнализирует при `windows-1251` или символах `�`.
- **Охрана в репозитории:** добавить pre-commit/CI шаг, запрещающий появление строки `windows-1251` в новых коммитах.
- **Документация:** обновить README и `DOROZHNAYA_KARTA.md` по итогам деплоя (какие проверки пройдены, где лежат логи).
