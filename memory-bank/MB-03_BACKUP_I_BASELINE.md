# MB-03 — Бэкапы и baseline

- **Контрольные суммы:**
  - `python tools/generate_md5_baseline.py` → `snapshot/baseline_md5.txt.gz` (gzip, хранится вне git).
  - При необходимости распаковать: `gzip -dc snapshot/baseline_md5.txt.gz > baseline_md5.txt` (локально).
- **Архив репозитория:** `git archive --format=tar --output baseline_snapshot.tar HEAD` (хранить вне git).
- **Оффлайн-слепок:** `tar -czf snapshot/nlping_ru_snapshot.tar.gz nlping.ru` и `python tools/generate_seo_baseline.py` → `snapshot/seo_baseline.json.gz` (каталог `snapshot/` занесён в `.gitignore`, в git остаётся только `.gitkeep`).
- **Перед крупным шагом:** убедись, что свежие gzip-файлы лежат локально; в репозиторий добавлять не нужно.
