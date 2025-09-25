# MB-07 — Деплой и охрана

- **Cloudflare Pages:**
  - Деплой инициируется пушем в `work` (или main) — проверяй статус в панели.
  - После деплоя всегда выполняй `Purge Everything`.
- **Smoke-тест после деплоя:**
  - `python tools/check_links.py --manifest tools/url_manifest.txt --base https://<project>.pages.dev`.
  - `python tools/check_utf8.py --manifest tools/url_manifest.txt --base https://<project>.pages.dev`.
  - Повторить для `https://nlping.ru` (когда домен подключён).
- **Мониторинг:** завести cron/CI-скрипт, который раз в сутки прогоняет `tools/check_utf8.py` и сигнализирует при `windows-1251` или символах `�`.
- **Охрана в репозитории:** добавить pre-commit/CI шаг, запрещающий появление строки `windows-1251` в новых коммитах.
- **Документация:** обновить README и `DOROZHNAYA_KARTA.md` по итогам деплоя (какие проверки пройдены, где лежат логи).
