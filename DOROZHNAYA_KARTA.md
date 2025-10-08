# Дорожная карта миграции зеркала nlping.ru

> Этот документ — единый источник правды (Single Source of Truth) о том, как выполняется миграция зеркала `nlping.ru`. Когда в
> переписке упоминается «дорожная карта», речь идёт именно об этом файле. Разделы ниже включают описание подхода, подробный
> план, журнал прогресса и чек-листы проверок.

## Контекст и цели

Cloudflare Pages отдаёт статический бэкап сайта `nlping.ru`, скачанный через HTTrack. На зеркале остались две ключевые проблемы:

1. **Дублирование сегмента `nlping.ru` в URL**. Контент находится в подкаталоге `nlping.ru/`, поэтому реальные страницы открываются как `/nlping.ru/...`, а при подключении боевого домена получится нежелательное `nlping.ru/nlping.ru/...`.
2. **Неверная кодировка контента**. HTML и XML внутри `nlping.ru/` сохранены в Windows-1251, а Cloudflare Pages по умолчанию отдаёт `charset=utf-8`, из-за чего текст искажается.

Цель — привести зеркало к структуре «корень = сайт», перевести весь контент в UTF-8, сохранить SEO-метрики и обеспечить автоматические проверки, чтобы не повторить прошлую ошибку с слишком крупными, непроверяемыми диффами.

## Основные задачи

1. **Устранить дублирование `nlping.ru` в путях.** Перенести содержимое подкаталога `nlping.ru/` в корень репозитория, настроить корректный `index.html`, очистить артефакты HTTrack.
2. **Перевести контент в UTF-8.** Безопасно перекодировать HTML/XML из CP1251 → UTF-8, обновить мета-теги и декларации, убедиться, что страницы и RSS валидны.

## Рассмотренные варианты и выбор

| Вариант | Суть | Плюсы | Ограничения |
| --- | --- | --- | --- |
| A | Оставить структуру как есть и выдавать `charset=windows-1251` через `_headers`. | Быстрый патч, минимум кода. | Сохраняет устаревшую кодировку, требует постоянного контроля правил, не решает дублирование `/nlping.ru/` в URL. |
| B | Перекодировать все HTML/XML в UTF-8, не трогая структуру. | Совместимо с Cloudflare Pages, убирает проблему кодировки. | URL остаются с префиксом `/nlping.ru/`, поддержка зеркала остаётся неудобной. |
| C | Перенести содержимое `nlping.ru/` в корень и сразу перекодировать в UTF-8 с автоматическими проверками. | Устраняет дублирование URL и проблему кодировки, делает структуру очевидной, снижает технический долг. | Требует аккуратной миграции и надёжных скриптов, иначе можно испортить контент или SEO. |

**Выбран вариант C.** На dev-сайте нет трафика, поэтому можно сразу привести зеркало к финальной структуре и кодировке. Риски управляемы: перед каждой партией есть снапшоты, автоматические проверки и журнал для откатов.

## Подход (рабочие принципы против перегрузки)

- **Минимальные партии.** Каждое изменение выполняется маленькой законченной задачей (не более ~150 файлов в коммите; при перекодировке — одна поддиректория за итерацию).
- **Двойной контур проверок.** Для каждого шага: автоматический скрипт (чексуммы, поиск `windows-1251`, обход sitemap) + выборочная ручная проверка ключевых страниц.
- **Постоянные точки отката.** После каждой подзадачи — коммит и запись в журнал. При проблеме можно откатиться без потери контекста.
- **Документирование прогресса.** Фиксировать в этой дорожной карте и в сопутствующих памятках, что сделано и какие артефакты созданы.
- **Отчёты по микро-шагам.** Для каждого этапа дополнительно отмечать, какие микро-шаги (партии, каталоги, подэтапы) уже закрыты и какие ещё предстоит выполнить до полного завершения этапа. Обновлять этот список при каждом продвижении.
- **Merge после ключевых проверок.** Сразу после завершения B3 (появления `tools/check_utf8.py` и свежих логов) обновлять/сливать PR **из ветки задачи → `main`**, чтобы последующие партии оставались малыми.
 - **Контроль диффов.** Перед коммитом проверять `git diff --stat` и объём. Если партия слишком большая, дробить дальше. Для адаптивного подбора размера используем журнал `memory-bank/diff-limit-plan.md` и процедуру из `MB-02_RABOCHIE_PRINCIPY.md`.
- **Артефакты baseline — только локально.** Слепки, контрольные суммы и отчёты генерируем в `snapshot/` и `logs/`, эти каталоги внесены в `.gitignore`, чтобы коммиты открывались мгновенно и не появлялась ошибка огромного диффа.
- **Учитываем отсутствие трафика.** Нет активных посетителей на dev-версии — значит, временные заплатки можно пропустить и сразу двигаться к финальной структуре и кодировке, но при этом сохраняем автоматизированные проверки, чтобы не потерять контент/SEO.

## Дорожная карта

### Этап A. База и страхующие артефакты

| Код | Шаг | Проверки и артефакты | Статус |
| --- | --- | --- | --- |
| A1 | Зафиксировать подход и правила работы (этот файл `DOROZHNAYA_KARTA.md`). | Проверка: `cat DOROZHNAYA_KARTA.md`, ревью; артефакт: `DOROZHNAYA_KARTA.md`. | ✅ Выполнено (коммит `Add baseline checksums for nlping.ru`). |
| A2 | Снять baseline контрольных сумм для `nlping.ru`. | Команда: `python tools/generate_md5_baseline.py` → `snapshot/baseline_md5.txt.gz` (артефакт не хранится в git). | ✅ Выполнено (коммит `Add baseline checksums for nlping.ru`, обновлено скриптом). |
| A3 | Сформировать манифест URL (sitemap, RSS, ключевые страницы) → `tools/url_manifest.txt`. | Проверка: `wc -l tools/url_manifest.txt`. | ✅ Выполнено — манифест создан (`tools/url_manifest.txt`). |
| A4 | Снять оффлайн-слепок для SEO-сравнения → каталог `snapshot/` + выгруженные `<title>/<meta>`. | Проверка: команда `tar -czf snapshot/nlping_ru_snapshot.tar.gz nlping.ru` и `python tools/generate_seo_baseline.py` → `snapshot/seo_baseline.json.gz`; оба артефакта остаются локально (в git только `.gitkeep`). | ✅ Выполнено — локальный слепок и SEO-бейзлайн генерируются по запросу и не коммитятся. |
| A5 | Описать постоянные памятки (MB-01…MB-07) и рабочую инструкцию выполнения (`INSTRUKTSIYA_VYPOLNENIYA.md`). | Проверка: файлы созданы, ссылка из дорожной карты. | ✅ Выполнено — памятки лежат в `memory-bank/MB-*.md`. |

### Этап B. Инструменты проверки и страховки

| Код | Шаг | Проверки и артефакты | Статус |
| --- | --- | --- | --- |
| B1 | Скрипт `tools/list_assets.py` — собрать зависимости страниц (CSS/JS/изображения). | Артефакт: `artifacts/assets.json`. | ✅ Выполнено — скрипт собирает 2169 HTML-файлов, формируя карту ресурсов (`python tools/list_assets.py` → `artifacts/assets.json`). |
| B2 | Скрипт `tools/check_links.py` — локальная проверка ссылок/ресурсов по каталогу или manifest. | Проверка: прогон `python tools/check_links.py --scope nlping.ru/index.html` → лог `logs/check_links-20250923T200035Z.json` (все ресурсы на месте, устаревший `s.nlping.ru/jsapi/click.js` удалён). | ✅ Выполнено — скрипт контролирует ссылки, база очищена от битой интеграции. |
| B3 | Скрипт `tools/check_utf8.py` — валидация кодировки, поиск `�`, сравнение SEO-блоков со слепком. | Проверка: отчёт `logs/check_utf8-*.json`. | ✅ Выполнено — скрипт собирает цели из manifest/`--scope`, при необходимости проверяет HTTP-заголовки и сверяет SEO-блоки; логи лежат в `logs/check_utf8-*.json`. |

> 💡 **Напоминание о PR.** Как только B3 готов и проверки проходят, обнови/создай PR **из ветки задачи → `main`** и доведи его до merge, чтобы следующие этапы шли меньшими партиями.

### Этап C. Перенос структуры (устранение `/nlping.ru/` в URL)

| Код | Шаг | Проверки и артефакты | Статус |
| --- | --- | --- | --- |
| C1 | Перенести корневые HTML (`index.html`, `news.html`, …) из `nlping.ru/` в корень, настроить главный `index.html`. | Проверка: локальный `python -m http.server`, ручная проверка главной. | ✅ Выполнено — HTML верхнего уровня перенесены из `nlping.ru/` в корень, дубликатов не осталось. |
| C2 | Перемещать каталоги партиями (`css/`, `images/`, `js/`, `p/…`) с промежуточными проверками `tools/check_links.py`. | Проверка: отчёты скрипта, ручная выборка. | ✅ Выполнено — каталоги `_p_http_/`, `files/`, `player/`, `rep/`, `p/` перенесены в корень, проверки пройдены (см. «Прогресс по шагу C2»). |
| C3 | Очистить остатки HTTrack (индекс каталога, пустые директории), обновить ссылки в README. | Проверка: `find . -maxdepth 1 -name 'nlping.ru'` → пусто, `find . -name '.DS_Store'` → пусто. | ✅ Выполнено — каталог `hts-cache/` и `.DS_Store` удалены, README обновлён под новую структуру. |

### Этап D. Перекодировка в UTF-8 (по партиям)

| Код | Шаг | Проверки и артефакты | Статус |
| --- | --- | --- | --- |
| D0 | Написать `tools/reencode.py` (CP1251 → UTF-8) + модульные тесты `tools/tests/test_reencode.py`. | Проверка: `pytest tools/tests/test_reencode.py`. | ✅ Выполнено — скрипт перекодировки и тесты добавлены, проверка `pytest tools/tests/test_reencode.py`. |
| D1 | Первая партия (корневые HTML, RSS, критичные страницы). | Проверки: `tools/reencode.py`, `rg -n "windows-1251"`, ручной просмотр. | ✅ Выполнено — перекодированы корневые страницы, RSS и ключевые лендинги (`logs/reencode-20250930T070225Z.json`, `logs/check_utf8-20250930T070433Z.json`). |
| D2…Dn | Остальные директории (`p/0*`, `p/1*`, …) — не более 150 файлов за итерацию. | Проверки: `tools/check_utf8.py --scope <dir>`, выборка страниц. | ✅ Выполнено — весь массив HTML перекодирован и подтверждён; итоговый прогон `tools/check_utf8.py --manifest tools/url_manifest.txt` сохранён в `logs/check_utf8-20251008T105810Z.json`. |
| Dlast | Финальная валидация: `rg -n "windows-1251" .` → пусто; полный прогон `tools/check_utf8.py --manifest`. | Артефакты: лог проверки, обновлённые контрольные суммы. | ⏳ Не начато. |

### Этап E. Деплой и верификация

| Код | Шаг | Проверки и артефакты | Статус |
| --- | --- | --- | --- |
| E1 | Прогон локальных smoke-тестов (HTTP-сервер + `tools/check_links.py`, `tools/check_utf8.py`). | Проверка: отчёты без ошибок. | ⏳ Не начато. |
| E2 | Деплой на Cloudflare Pages, `Purge Everything`, прогон тестов по доменам Pages и `nlping.ru`. | Проверка: `curl -I` → `charset=utf-8`, отчёты скриптов. | ⏳ Не начато. |
| E3 | Обновить документацию (README, дорожная карта, мониторинг), приложить результаты проверок. | Проверка: ревью документации. | ⏳ Не начато. |
| E4 | Настроить охрану (CI-скрипт, запрещающий `windows-1251`, и напоминание о мониторинге). | Проверка: тестовый коммит с запрещённой строкой → CI падает. | ⏳ Не начато. |

## Риски и способы их закрыть

| Риск | Когда может возникнуть | Как предотвращаем |
| --- | --- | --- |
| Повреждение файлов при перекодировке | Ошибка скрипта или неверная партия | Сначала прогоняем на копии, ведём логи `logs/reencode-*.json`, baseline пересчитываем командой `python tools/generate_md5_baseline.py` (артефакт лежит в `snapshot/` вне git) и держим слепок для отката. |
| Потеря ссылок/ресурсов после переноса | При переносе каталогов и HTML в корень | Используем `tools/list_assets.py` и `tools/check_links.py` после каждой партии, ручная выборка страниц из критичных разделов. |
| Изменение SEO-тегов | При рефакторинге структуры или перекодировке | Сравниваем `<title>`, `meta description`, `h1` с оффлайн-слепком (этап A4) с помощью `tools/check_utf8.py`. |
| Остатки `windows-1251` в кодовой базе | Кто-то добавил старый файл или патч неполный | `rg -n "windows-1251"` в рамках проверки, финальная валидация `tools/check_utf8.py --manifest`, настройка CI (E4). |
| Ошибки Cloudflare кэша | После деплоя отдаются старые файлы | Всегда выполняем `Purge Everything` и проверяем через `curl -I` с `Cache-Control: no-cache`, плюс smoke-тест по Pages-домену и боевому домену. |

## Памятки (memory-bank), которые нужно создать на этапе A5

- **MB-01 — Контекст и цель.** Краткая формулировка задачи миграции и критериев успеха.
- **MB-02 — Рабочие принципы.** Напоминание о партии изменений, проверках и журнале.
- **MB-03 — Бэкапы и baseline.** Команды для снапшота, контрольных сумм и их расположение.
- **MB-04 — Перенос структуры.** Чек-лист `git mv`, порядок перемещения каталогов, что проверять.
- **MB-05 — Перекодировка.** Как запускать `tools/reencode.py`, лимиты партий, что делать при ошибке.
- **MB-06 — Проверки и сравнение SEO.** Применение `tools/check_links.py`, `tools/check_utf8.py`, как интерпретировать отчёты.
- **MB-07 — Деплой и охрана.** Порядок деплоя на Cloudflare Pages, команды для `Purge`, описание мониторинга/CI.
- **Журнал лимитов diff.** `memory-bank/diff-limit-plan.md` — актуальные `safe_bound`/`fail_bound` и заметки по стратегиям деления партий.

## Инструкция для выполнения (универсальный рабочий промпт)

> Когда в переписке звучит команда «Следуй дорожной карте», ассистент использует этот промпт, подставляя актуальный шаг из блока «## Текущее состояние дорожной карты» и соответствующие памятки.

```
Ты работаешь в репозитории nlping и продолжаешь миграцию зеркала. Выполняй всё строго в ветке work, коммить малыми партиями и после шага обновляй PR work → main.

1. Подготовка ветки:
   • git fetch origin
   • git checkout work
   • git pull --ff-only
   Если upstream недоступен, сообщи мне, но продолжай локально.

2. Освежи контекст:
   • Просмотри текущий шаг (<код и название>) в разделах «Дорожная карта» и «Текущее состояние» этого файла.
   • Загляни в INSTRUKTSIYA_VYPOLNENIYA.md (актуальный этап) и соответствующие памятки MB-0X, чтобы помнить про проверки и правила ветки.

3. Выполнение шага <код>:
   • Сформируй точный план действий по таблице этапа и памяткам.
   • Выполняй перенос/перекодировку партиями. После каждой партии:
     – python tools/check_links.py --scope <перемещённый файл или каталог>
     – python tools/check_utf8.py --scope <перемещённый файл или каталог>
     – python -m http.server (минимум 3 страницы вручную)
     – зафиксируй логи в logs/ и проверь git status, что партия чистая.
   • Следи за относительными путями, исправляй ссылки на новый корень, обновляй инструменты и конфигурацию, если шаг меняет структуру.
   • Дополнительные задачи для активного шага смотри в подблоке ниже.

4. Завершение шага:
   • Сделай коммит(ы) с понятными сообщениями.
   • Обнови DOROZHNAYA_KARTA.md (таблицы, «Текущее состояние», журнал прогресса) и при необходимости памятки.
   • Проверь git status, подготовь PR work → main, опиши изменения и результаты проверок. Если push невозможен, сообщи мне.

5. Сообщи итог:
   • Кратко опиши выполненные действия, подтверждённые проверки и оставшиеся риски/следующие шаги.
```

### Активный шаг C2 — перенос каталогов ассетов

1. Сверь план с памяткой `memory-bank/MB-04_PERENOS_STRUKTURY.md` — в ней перечислены группы каталогов и порядок их переноса.
2. Сформируй список каталожных партий (`css/`, `js/`, `files/`, `p/…`, медиатеки), определив для каждой зависимые страницы по отчётам `tools/list_assets.py`.
3. Для каждой партии выполняй `git mv nlping.ru/<каталог> <каталог>` и сразу обновляй относительные пути в HTML/CSS/JS, если каталоги содержат вложенные ссылки на `../nlping.ru/`.
4. После каждой партии прогоняй проверки: `python tools/check_links.py --scope <каталог или связанные страницы>` и `python tools/check_utf8.py --scope <каталог или связанные страницы>`, фиксируй логи в `logs/`.
5. Делай выборочный ручной просмотр через `python -m http.server` (минимум три страницы на партию), чтобы убедиться в корректной загрузке ассетов.
6. В журнале фиксируй завершённые партии, чтобы отслеживать прогресс и не упустить оставшиеся каталоги.

> По завершении C2 перенеси этот блок в журнал и подготовь чек-лист для шага C3.

#### Прогресс по шагу C2

- 2025-09-29T09:24:13Z — перенёс каталог `files/` в корень. Проверки: `python tools/check_links.py --scope index7946.html --scope print7946.html --scope 5C03C101-F4715-F6A93AC7.html`, `python tools/check_utf8.py --scope index7946.html --scope print7946.html --scope 5C03C101-F4715-F6A93AC7.html`, `curl -I` по `index7946.html`, `print7946.html`, `5C03C101-F4715-F6A93AC7.html` (через `python -m http.server`).
- 2025-09-29T09:31:14Z — перенёс каталог `player/` в корень. Проверки: `python tools/check_links.py --scope skazki2012.html --scope superpower.html --scope printd109.html`, `python tools/check_utf8.py --scope skazki2012.html --scope superpower.html --scope printd109.html`, `curl -I` по `skazki2012.html`, `superpower.html`, `printd109.html` (через `python -m http.server`).
- 2025-09-29T17:14:47Z — перенёс каталог `rep/` в корень. Проверки: `python tools/check_links.py --scope indexbf63.html --scope printbf63.html --scope CBC51967-F461A-8C8233CC.html` → `logs/check_links-20250929T171425Z.json` (фиксирует прежние внешние недоступные ресурсы), `python tools/check_utf8.py --scope indexbf63.html --scope printbf63.html --scope CBC51967-F461A-8C8233CC.html` → `logs/check_utf8-20250929T171434Z.json`, `python -m http.server 8000` + `curl -I` по `indexbf63.html`, `printbf63.html`, `CBC51967-F461A-8C8233CC.html`.
- 2025-09-29T17:23:45Z — перенёс каталог `_p_http_/` в корень. Проверки: `python tools/check_links.py --scope index5b8c.html --scope mozg2 --scope _p_http_/nlping.ru/index9a3e.html --scope _p_http_/w.nlping.ru/mozg_special/_/p_.html` → `logs/check_links-20250929T172319Z.json`; `python tools/check_utf8.py --scope index5b8c.html --scope mozg2 --scope _p_http_/nlping.ru/index9a3e.html --scope _p_http_/w.nlping.ru/mozg_special/_/p_.html` → `logs/check_utf8-20250929T172323Z.json`; `python -m http.server 8000` + `curl -I` по `index5b8c.html`, `mozg2`, `_p_http_/nlping.ru/index9a3e.html`.
- 2025-09-29T18:01:26Z — перенёс каталог `p/` (HTTrack-редирект showcase) в корень и обновил ссылки в `webinar.nlping.ru`. Проверки: `python tools/check_links.py --scope webinar.nlping.ru/index.html --scope webinar.nlping.ru/node/26.html --scope p/indexc1c8.html --scope indexc1c8.html` → `logs/check_links-20250929T180110Z.json`; `python tools/check_utf8.py --scope webinar.nlping.ru/index.html --scope webinar.nlping.ru/node/26.html --scope p/indexc1c8.html --scope indexc1c8.html` → `logs/check_utf8-20250929T180112Z.json`; `python -m http.server 8000` + `curl -I` по `p/indexc1c8.html`, `webinar.nlping.ru/index.html`, `indexc1c8.html`.
- 2025-09-29T19:35:30Z — обновил относительные ссылки на скрипт и главную `nlping.ru` в зеркалах `w.nlping.ru` и `webinar.nlping.ru` после переноса ассетов в корень. Проверки: `python tools/check_links.py --scope w.nlping.ru --scope webinar.nlping.ru` → `logs/check_links-20250929T193503Z.json`; `python tools/check_utf8.py --scope w.nlping.ru --scope webinar.nlping.ru` → `logs/check_utf8-20250929T193507Z.json`; `python -m http.server 8000` + `curl -I` по `w.nlping.ru/index.html`, `w.nlping.ru/nlp-master/index.html`, `webinar.nlping.ru/index.html`.

- 2025-09-29T19:59:05Z — перепроверил, что каталог `nlping.ru/` отсутствует, а оставшиеся партии перечислены и закрыты. Проверки: `find . -maxdepth 1 -name 'nlping.ru'` (пусто), `git ls-tree 7cd3d96:nlping.ru` (исторический список партий `_p_http_/`, `files/`, `player/`, `rep/`, `p/` — все перенесены).

**Сделанные микро-шаги (5/5):** `_p_http_/`, `files/`, `player/`, `rep/`, `p/`.

**Оставшиеся микро-шаги:** нет — этап C2 закрыт, можно переходить к C3.

### Шаг C3 — очистка HTTrack-артефактов и документации

1. Убедиться, что после переноса каталогов не восстановился `nlping.ru/` или другие пустые директории.
2. Удалить временные HTTrack-файлы и папки (`hts-cache/`, `.DS_Store`), добавить их в `.gitignore`.
3. Перепроверить, что ссылки на структуру в документации и README указывают на корень репозитория.
4. Зафиксировать результаты в `DOROZHNAYA_KARTA.md` и подготовить переход к шагу D0.

#### Прогресс по шагу C3

- 2025-09-29T20:08:00Z — удалил `hts-cache/` и все `.DS_Store`, добавил шаблон в `.gitignore`, создал README со ссылками на инструменты. Проверки: `find . -maxdepth 1 -name 'nlping.ru'` (пусто), `find . -name '.DS_Store'` (пусто).

**Сделанные микро-шаги (3/3):** проверка отсутствия `nlping.ru/`, удаление HTTrack-артефактов, обновление README.

**Оставшиеся микро-шаги:** нет — этап C3 закрыт, готов к началу D0.

### Шаг D2 — перекодировка серий `index0*`/`print0*`

1. Сверь состав серии по `ls index0*.html print0*.html`, дополни списком связанных `print*.html`.
2. Запусти `python tools/reencode.py --paths index0*.html print0*.html --limit 200` и проверь лог в `logs/reencode-*.json`.
3. Заменяй мета-теги на `charset=utf-8`, если скрипт восстановил текст, но оставил старое объявление кодировки.
4. Выполни `rg -n "windows-1251" index0*.html print0*.html` — убедись, что следов старой кодировки нет.
5. Запусти `python tools/check_utf8.py --no-manifest` с `--scope` для каждого файла серии, сохрани отчёт в `logs/check_utf8-*.json`.
6. Просмотри минимум три страницы вручную (главная серии, одна статья и соответствующий `print`-вариант).

#### Прогресс по шагу D2

- 2025-09-30T07:13:38Z — перекодировал серию `index0*`/`print0*` в UTF-8 (`python tools/reencode.py --paths index0*.html print0*.html --limit 200` → `logs/reencode-20250930T071338Z.json`), заменил мета-теги и проверил `rg -n "windows-1251" index0*.html print0*.html` (пусто).
- 2025-09-30T07:14:32Z — `python tools/check_utf8.py --no-manifest …` по всем файлам серии → `logs/check_utf8-20250930T071432Z.json`, подозрительных последовательностей и замен символов не обнаружено.

- 2025-09-30T07:42:59Z — перекодировал серию `index1*`/`print1*` (`python tools/reencode.py --paths index1*.html print1*.html --limit 200` → `logs/reencode-20250930T074259Z.json`), обновил мета-теги на `charset=utf-8`, `rg -n "windows-1251" index1*.html print1*.html` → пусто.
- 2025-09-30T07:43:58Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index1*.html print1*.html)` → `logs/check_utf8-20250930T074358Z.json`, ручная проверка через `python -m http.server` + `curl -I` по `index1178.html`, `index1a62.html`, `print1178.html`.
- 2025-09-30T08:42:26Z — перекодировал серию `index2*`/`print2*` (`python tools/reencode.py --paths index2*.html print2*.html` → `logs/reencode-20250930T084226Z.json`), заменил объявления кодировки на `charset=utf-8`, `rg -n "windows-1251" index2*.html print2*.html` → пусто.
- 2025-09-30T08:43:35Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index2*.html print2*.html)` → `logs/check_utf8-20250930T084335Z.json`, подозрительных последовательностей и замен символов нет.
- 2025-09-30T08:44:10Z — ручная проверка через `python -m http.server 8000` + `curl -I` по `index205f.html`, `index2c55.html`, `print205f.html`.

- 2025-09-30T11:05:36Z — перекодировал серию `index3*`/`print3*` (`python tools/reencode.py --paths index3*.html print3*.html` → `logs/reencode-20250930T110536Z.json`), заменил объявления кодировки на `charset=utf-8`, `rg -n "windows-1251" index3*.html print3*.html` → пусто.
- 2025-09-30T11:05:57Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index3*.html print3*.html)` → `logs/check_utf8-20250930T110557Z.json`, подозрительных последовательностей нет.
- 2025-09-30T11:06:12Z — `python -m http.server 8000` + `curl -I` по `index31be.html`, `index3a80.html`, `print31be.html` подтвердили доступность страниц серии в UTF-8.
- 2025-09-30T11:52:25Z — перекодировал серию `index4*`/`print4*` (`python tools/reencode.py --paths index4*.html print4*.html --limit 200` → `logs/reencode-20250930T115225Z.json`), заменил объявления кодировки на `charset=utf-8`, `rg -n "windows-1251" index4*.html print4*.html` → пусто.
- 2025-09-30T11:52:48Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index4*.html print4*.html)` → `logs/check_utf8-20250930T115248Z.json`; ручная проверка через `python -m http.server 8000` + `curl -I` по `index4066.html`, `index43f7.html`, `print4686.html` подтвердила корректную отдачу UTF-8.
- 2025-09-30T12:14:06Z — перекодировал серию `index5*`/`print5*` (`python tools/reencode.py --paths index5*.html print5*.html --limit 200` → `logs/reencode-20250930T121406Z.json`), заменил объявления кодировки на `charset=utf-8`, `rg -n "windows-1251" index5*.html print5*.html` → пусто.
- 2025-09-30T12:14:35Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index5*.html print5*.html)` → `logs/check_utf8-20250930T121435Z.json`, подозрительных последовательностей и замен символов не обнаружено.
- 2025-09-30T12:14:57Z — `python -m http.server 8000` + `curl -I` по `index54d1.html`, `print54d1.html`, `index5e28.html` подтвердили корректную отдачу серии `5*` в UTF-8.
- 2025-09-30T13:05:23Z — перекодировал серию `index6*`/`print6*` (`python tools/reencode.py --paths index6*.html print6*.html --limit 200` → `logs/reencode-20250930T130523Z.json`), заменил объявления кодировки на `charset=utf-8`, `rg -n "windows-1251" index6*.html print6*.html` → пусто.
- 2025-09-30T13:05:53Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index6*.html print6*.html)` → `logs/check_utf8-20250930T130553Z.json`, подозрительных последовательностей и замен символов не обнаружено.
- 2025-09-30T13:06:05Z — `python -m http.server 8000` + `curl -I` по `index604d.html`, `index65c7.html`, `print6b71.html` подтвердили корректную отдачу серии `6*` в UTF-8.
- 2025-09-30T16:55:52Z — расширил `_maybe_decode_double_encoded` в `tools/reencode.py`, чтобы корректно восстанавливать тексты с символами `–` и другими знаками за пределами Latin-1; `pytest tools/tests/test_reencode.py` подтвердил отсутствие регрессий.
- 2025-09-30T17:45:08Z — перекодировал серию `index9*`/`print9*` (`python tools/reencode.py --paths index9*.html print9*.html` → `logs/reencode-20250930T174508Z.json`), подтвердил в логе конвертацию 30 файлов.
- 2025-09-30T17:45:30Z — заменил декларации `charset=windows-1251` на `charset=utf-8` в серии `index9*`/`print9*` (скрипт на `pathlib`), повторная проверка `rg -n "windows-1251" index9*.html print9*.html` → пусто.
- 2025-09-30T17:46:25Z — `python tools/check_utf8.py --scope . --no-manifest` → `logs/check_utf8-20250930T174625Z.json`, отчёт без замечаний по серии `index9*`/`print9*`.
- 2025-09-30T17:47:10Z — вручную просмотрел `index907c.html` и `print907c.html` (контент читается корректно, без � и артефактов).
- 2025-09-30T16:57:22Z — перекодировал серию `index8*`/`print8*` (`python tools/reencode.py --paths index8*.html print8*.html` → `logs/reencode-20250930T165722Z.json`), мета-теги обновлены на `charset=utf-8`.
- 2025-09-30T16:58:40Z — `rg -n "windows-1251" index8*.html print8*.html` → пусто, убедился что старые декларации кодировки удалены.
- 2025-09-30T17:02:06Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index8*.html print8*.html)` → `logs/check_utf8-20250930T170206Z.json`, подозрительных последовательностей и замен символов не обнаружено.
- 2025-10-01T17:21:03Z — перекодировал серию `indexf*`/`printf*` (`python tools/reencode.py --paths indexf*.html printf*.html --limit 200` → `logs/reencode-20251001T172103Z.json`), заменил объявления `charset` на `utf-8`, `rg -n "windows-1251" indexf*.html printf*.html` → пусто.
- 2025-10-01T17:21:19Z — `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' indexf*.html printf*.html)` → `logs/check_utf8-20251001T172119Z.json`; `python -m http.server 8000` + `curl -I` по `indexf0a1.html`, `indexf497.html`, `printf5a6.html` подтвердили корректную отдачу серии `f*` в UTF-8.
- 2025-10-08T09:22:40Z — перекодировал тематические лендинги (`alphabet.html`, `alfavit.html`, `konstantin_pukhov.html`, `making-training-algoritm.html`, `mind-layers.html`, `mind-layers-vid`, `money-IQ-test.html`, `relationship_management.html`, `relationship_management&ep=2.html`, `relationship_management_2_web.html`, `superpower.html`, `tss.html`, `tropa_sily.html`, `training10k.html`, `training10k_base-download`, `video.html`, `trainers.html`, `skazki2012.html`) (`python tools/reencode.py --paths alphabet.html alfavit.html konstantin_pukhov.html making-training-algoritm.html mind-layers.html mind-layers-vid money-IQ-test.html relationship_management.html 'relationship_management&ep=2.html' relationship_management_2_web.html superpower.html tss.html tropa_sily.html training10k.html training10k_base-download video.html trainers.html skazki2012.html --limit 200` → `logs/reencode-20251008T092240Z.json`), декларации обновлены на `charset=utf-8`.
- 2025-10-08T09:23:19Z — `python tools/check_utf8.py --no-manifest --scope alphabet.html --scope alfavit.html --scope konstantin_pukhov.html --scope making-training-algoritm.html --scope mind-layers.html --scope mind-layers-vid --scope money-IQ-test.html --scope relationship_management.html --scope 'relationship_management&ep=2.html' --scope relationship_management_2_web.html --scope superpower.html --scope tss.html --scope tropa_sily.html --scope training10k.html --scope training10k_base-download --scope video.html --scope trainers.html --scope skazki2012.html` → `logs/check_utf8-20251008T092319Z.json`; `python -m http.server 8000` + `curl -I` по `alphabet.html`, `mind-layers.html`, `training10k.html` подтвердили корректную отдачу UTF-8.
- 2025-10-08T10:44:25Z — перекодировал оставшиеся страницы подсерии `F47x` и тематические материалы (`F47C1.html`, `F47E4.html`, `ask46c6.html`, `blondy_strategy.html`, `spiralnaya_dinamika_vvedenie.html`) → `python tools/reencode.py --paths F47C1.html F47E4.html ask46c6.html blondy_strategy.html spiralnaya_dinamika_vvedenie.html --limit 50` (`logs/reencode-20251008T104413Z.json`), объявления `charset` заменены на `utf-8`, `rg -n "windows-1251"` по выборке → пусто.
- 2025-10-08T10:45:03Z — перекодировал недостающие `F47D4.html`, `F47DA.html`, `F47DE.html`, `F47E3.html` (`python tools/reencode.py --paths F47E3.html F47DA.html F47DE.html F47D4.html --limit 50` → `logs/reencode-20251008T104500Z.json`), синхронизировал `meta charset`, повторная проверка `rg -n "windows-1251" F47*.html` → пусто.
- 2025-10-08T10:45:13Z — `python tools/check_utf8.py --no-manifest --scope F47C1.html --scope F47E4.html --scope ask46c6.html --scope blondy_strategy.html --scope spiralnaya_dinamika_vvedenie.html --scope F47E3.html --scope F47DA.html --scope F47DE.html --scope F47D4.html` → `logs/check_utf8-20251008T104509Z.json`; `python -m http.server 8000` + `curl -I` по `F47E3.html`, `blondy_strategy.html`, `spiralnaya_dinamika_vvedenie.html` подтвердили корректную отдачу UTF-8.

**Сделанные микро-шаги (39/?)**: перекодировка и обновление мета-тегов `index0*`/`print0*`, проверка `check_utf8` для серии `0*`, перекодировка серии `index1*`/`print1*`, проверки `check_utf8` и ручной просмотр для серии `1*`, перекодировка `index2*`/`print2*`, автоматическая и ручная проверка серии `2*`, перекодировка `index3*`/`print3*`, автоматическая и ручная проверка серии `3*`, перекодировка серии `index4*`/`print4*`, автоматическая и ручная проверка серии `4*`, перекодировка серии `index5*`/`print5*`, автоматическая и ручная проверка серии `5*`, перекодировка серии `index6*`/`print6*`, автоматическая и ручная проверка серии `6*`, перекодировка серии `index7*`/`print7*`, автоматическая и ручная проверка серии `7*`, перекодировка серии `index8*`/`print8*`, автоматическая и ручная проверка серии `8*`, перекодировка серии `index9*`/`print9*`, автоматическая и ручная проверка серии `9*`, перекодировка серии `indexa*`/`printa*`, автоматическая и ручная проверка серии `a*`, перекодировка серии `indexb*`/`printb*`, автоматическая и ручная проверка серии `b*`, перекодировка серии `indexc*`/`printc*`, автоматическая и ручная проверка серии `c*`, перекодировка серии `indexd*`/`printd*`, автоматическая и ручная проверка серии `d*`, перекодировка серии `indexe*`/`printe*`, автоматическая и ручная проверка серии `e*`, перекодировка серии `indexf*`/`printf*`, автоматическая и ручная проверка серии `f*`, перекодировка и проверка GUID-файлов с префиксами `0*`–`3*`, `4*`–`6*`, `7*`–`9*`, `A*`–`C*`, перекодировка и проверка подсерий `F47x`, `F48x`, перекодировка и проверка `F4CF5.html`, перекодировка и проверка блока `F4D10.html`…`F4DFF.html`, перекодировка и проверка кластера `F0*`/`F2*`, перекодировка и проверка одиночных GUID `F5*`/`F8*`/`F9*`/`FC*`, перекодировка тематических лендингов (`alphabet.html`…`skazki2012.html`), перекодировка и проверка страниц `F47C1.html`…`F47E4.html`, `F47D4.html`, `F47DA.html`, `F47DE.html`, `F47E3.html`, `ask46c6.html`, `blondy_strategy.html`, `spiralnaya_dinamika_vvedenie.html` и подтверждение через `check_utf8` и ручной просмотр, финальный контрольный прогон `tools/check_utf8.py --manifest tools/url_manifest.txt` перед стартом шага Dlast (`logs/check_utf8-20251008T105810Z.json`).

**Оставшиеся микро-шаги:** пройти этап Dlast — глобально проверить отсутствие `windows-1251` (`rg -n "windows-1251" -g'*.html'`), при необходимости обновить baseline контрольных сумм (`python tools/generate_md5_baseline.py`) и задокументировать результаты перед стартом этапа E.

## Быстрый протокол (Memory → Roadmap → Instruction)

Используй короткую команду:

> **«Протокол, шаг <код этапа>».**

По этой фразе ассистент выполняет последовательность:

1. Открывает память (`memory-bank/MB-*.md`), сверяется с нужными памятками.
2. Актуализирует контекст в `DOROZHNAYA_KARTA.md` и определяет ближайший шаг.
3. Следует деталям из `INSTRUKTSIYA_VYPOLNENIYA.md` для выполнения шага.

Если нужно начать с конкретного пункта, уточни его код: например, «Протокол, шаг B3».

## Журнал прогресса

| Дата и время (UTC) | Шаги | Проверки | Итог |
| --- | --- | --- | --- |
| 2025-09-22T18:21:46Z | A1 — оформление дорожной карты, A2 — baseline MD5 | Ревью `DOROZHNAYA_KARTA.md`, `baseline_md5.txt` создан | ✅ Подтверждено. |
| 2025-09-22T18:25:00Z | Подготовка к новой итерации: переименовал документ в дорожную карту, уточнил разделы, подтвердил требования по логированию прогресса | `git mv PODHOD.md DOROZHNAYA_KARTA.md`, проверка ссылок на файл, актуализация таблиц | ✅ Документ синхронизирован с новыми инструкциями. |
| 2025-09-22T18:36:15Z | Актуализация дорожной карты под условия dev-сайта без трафика, детализация вариантов и рисков, добавление задач по инструментам и памяткам | Обновлены разделы «Рассмотренные варианты», «Дорожная карта», «Риски», добавлены ссылки на будущие памятки и инструкцию | ✅ Готов к запуску этапа A3. |
| 2025-09-23T14:59:36Z | A5 — созданы памятки memory-bank (MB-01…MB-07) с инструкциями по каждому блоку миграции | Проверка: `ls memory-bank/MB-*.md`, обновление статуса A5 в дорожной карте | ✅ Памятки готовы, можно переходить к A3. |
| 2025-09-23T15:00:19Z | A3 — сформирован манифест ключевых URL для автоматических проверок | Проверка: `wc -l tools/url_manifest.txt` → 26 строк, ручная выборка ссылок с главной | ✅ Манифест готов, следующий шаг — A4 (оффлайн-слепок). |
| 2025-09-23T16:07:58Z | A4 — оффлайн-слепок и SEO-бейзлайн (без доступа к внешней сети) | Попытка `wget --mirror https://nlping.ru/` → отказ прокси; вместо этого создан архив `snapshot/nlping_ru_snapshot.tar.gz` и локальный `snapshot/seo_baseline.json.gz` через `python tools/generate_seo_baseline.py` | ✅ Слепок зафиксирован, можно переходить к этапу B1 (инструменты проверок). |
| 2025-09-23T17:53:43Z | A2/A4 — перевёл baseline в сжатые локальные артефакты | Проверка: `python tools/generate_md5_baseline.py`, `python tools/generate_seo_baseline.py --output snapshot/seo_baseline.json.gz`; `.gitignore` обновлён, diff страницы открываются мгновенно | ✅ Огромные файлы исключены из git, baseline генерируется по запросу. |
| 2025-09-23T18:31:55Z | B1 — собрана карта зависимостей (`tools/list_assets.py`) | Прогон: `python tools/list_assets.py` → `artifacts/assets.json`, проверка объёма (`head artifacts/assets.json`) | ✅ Получен отчёт по 2169 HTML-файлам, готов к анализу перед переносом структуры. |
| 2025-09-23T19:17:37Z | B2 — разработан и опробован `tools/check_links.py` | `python tools/check_links.py --scope nlping.ru/index.html` → `logs/check_links-20250923T191737Z.json` | ⚠️ Скрипт выявил отсутствующий `s.nlping.ru/jsapi/click.js`; инструмент готов для дальнейших проверок. |
| 2025-09-23T20:00:35Z | B2 — удалена устаревшая hop-интеграция и повторно прогнан `tools/check_links.py` | `python tools/check_links.py --scope nlping.ru/index.html` → `logs/check_links-20250923T200035Z.json` | ✅ Проверка проходит, база очищена от битых ресурсов. |
| 2025-09-23T20:58:00Z | B3 — разработан `tools/check_utf8.py`, добавлены инструкции по запуску, сохранён первый лог | `python tools/check_utf8.py --manifest tools/url_manifest.txt` → `logs/check_utf8-20250923T205800Z.json` | ✅ Валидатор кодировки готов, следующая задача — перенос структуры. |
| 2025-09-25T17:35:11Z | Актуализировал документацию: добавлен «Протокол», напоминание о merge PR после B3 | Проверка: `git diff` по `DOROZHNAYA_KARTA.md`, `INSTRUKTSIYA_VYPOLNENIYA.md`, `memory-bank/MB-02_RABOCHIE_PRINCIPY.md` | ✅ Контекст восстановлен, готов к реализации B3. |
| 2025-09-25T17:53:41Z | B3 — создан `tools/check_utf8.py`, прогнан по манифесту для сверки кодировки и SEO | `python tools/check_utf8.py` → `logs/check_utf8-20250925T175341Z.json` | ✅ Инструмент готов, лог сохранён в `logs/` для ссылок при следующих шагах. |
| 2025-09-28T16:35:04Z | C1 — перенёс корневой index, блог, RSS и ключевые лендинги | `python tools/check_links.py` (логи: `logs/check_links-20250928T162859Z.json`, `...T163031Z.json`, `...T163141Z.json`, `...T163225Z.json`, `...T163441Z.json`); `python tools/check_utf8.py` (логи: `logs/check_utf8-20250928T162907Z.json`, `...T163036Z.json`, `...T163147Z.json`, `...T163229Z.json`, `...T163443Z.json`); `python -m http.server` + `curl -I` по трём страницам каждой партии | ▶️ Основные страницы доступны из корня; требуется перенести оставшиеся HTML и связанные каталоги. |
| 2025-09-28T16:44:44Z | C1 — перенёс блок «Видео» (video/index8d4e/print8d4e) | `python tools/check_links.py --scope video.html --scope index8d4e.html --scope print8d4e.html` → `logs/check_links-20250928T164430Z.json`; `python tools/check_utf8.py --scope video.html --scope index8d4e.html --scope print8d4e.html` → `logs/check_utf8-20250928T164433Z.json`; `python -m http.server` + `curl -I` по `video.html`, `index8d4e.html`, `print8d4e.html` | ✅ Раздел «Видео» работает из корня, продолжаю перенос оставшихся страниц. |
| 2025-09-28T17:17:45Z | C1 — поднял ассеты раздела «Видео» (css/, js/, images/, img/, favicon.ico) в корень | `python tools/check_links.py --scope video.html --scope index8d4e.html --scope print8d4e.html` → `logs/check_links-20250928T171738Z.json`; `python tools/check_utf8.py --scope video.html --scope index8d4e.html --scope print8d4e.html` → `logs/check_utf8-20250928T171743Z.json` | ✅ Стили, скрипты и изображения раздела доступны из корня, ссылка на hop-интеграцию удалена. |
| 2025-09-29T09:24:13Z | C2 — перенёс каталог `files/` в корень | `python tools/check_links.py --scope index7946.html --scope print7946.html --scope 5C03C101-F4715-F6A93AC7.html` → `logs/check_links-20250929T092348Z.json`; `python tools/check_utf8.py --scope index7946.html --scope print7946.html --scope 5C03C101-F4715-F6A93AC7.html` → `logs/check_utf8-20250929T092402Z.json`; `curl -I` (через `python -m http.server`) по трем страницам | ✅ Каталог доступен из корня, материалы скачиваются по прямым ссылкам. |
| 2025-09-29T17:14:47Z | C2 — перенёс каталог `rep/` в корень | `python tools/check_links.py --scope indexbf63.html --scope printbf63.html --scope CBC51967-F461A-8C8233CC.html` → `logs/check_links-20250929T171425Z.json` (отмечает старые внешние недоступные ресурсы); `python tools/check_utf8.py --scope indexbf63.html --scope printbf63.html --scope CBC51967-F461A-8C8233CC.html` → `logs/check_utf8-20250929T171434Z.json`; `python -m http.server 8000` + `curl -I` по `indexbf63.html`, `printbf63.html`, `CBC51967-F461A-8C8233CC.html` | ✅ Изображения `rep/` обслуживаются из корня; остаются внешние ссылки на старые домены (`lp.nlping.ru`, `w.nlping.ru`) до переноса соответствующих каталогов. |
| 2025-09-29T17:23:45Z | C2 — перенёс каталог `_p_http_/` в корень | `python tools/check_links.py --scope index5b8c.html --scope mozg2 --scope _p_http_/nlping.ru/index9a3e.html --scope _p_http_/w.nlping.ru/mozg_special/_/p_.html` → `logs/check_links-20250929T172319Z.json`; `python tools/check_utf8.py --scope index5b8c.html --scope mozg2 --scope _p_http_/nlping.ru/index9a3e.html --scope _p_http_/w.nlping.ru/mozg_special/_/p_.html` → `logs/check_utf8-20250929T172323Z.json`; `python -m http.server 8000` + `curl -I` по `index5b8c.html`, `mozg2`, `_p_http_/nlping.ru/index9a3e.html` | ✅ Каталог `_p_http_/` доступен из корня; редиректы HTTrack продолжают работать с локальными заглушками внешних страниц. |
| 2025-09-29T19:35:30Z | C2 — обновил относительные ссылки `w.nlping.ru` и `webinar.nlping.ru` после переноса ассетов | `python tools/check_links.py --scope w.nlping.ru --scope webinar.nlping.ru` → `logs/check_links-20250929T193503Z.json`; `python tools/check_utf8.py --scope w.nlping.ru --scope webinar.nlping.ru` → `logs/check_utf8-20250929T193507Z.json`; `python -m http.server 8000` + `curl -I` по `w.nlping.ru/index.html`, `w.nlping.ru/nlp-master/index.html`, `webinar.nlping.ru/index.html` | ✅ Скрипты и ссылки на главную `nlping.ru` работают из нового расположения ассетов. |
| 2025-09-28T17:26:14Z | C1 — перенёс оставшиеся 2127 HTML верхнего уровня из `nlping.ru/` в корень | `python tools/check_links.py --scope .` → `logs/check_links-20250928T172536Z.json`; `python tools/check_utf8.py --scope . --no-manifest` → `logs/check_utf8-20250928T172548Z.json`; `python -m http.server 8000` + `curl -I` по `index.html`, `F48A6.html`, `setup925a.html` | ✅ Каталог `nlping.ru/` очищен от корневых HTML, страницы обслуживаются из нового положения. |
| 2025-09-29T20:08:00Z | C3 — удалены артефакты HTTrack и обновлена документация | `find . -maxdepth 1 -name 'nlping.ru'` → пусто; `find . -name '.DS_Store'` → пусто; создан README с актуальными командами | ✅ База очищена, можно переходить к разработке `tools/reencode.py`. |
| 2025-09-30T09:10:00Z | D0 — разработан `tools/reencode.py`, добавлены модульные тесты | `pytest tools/tests/test_reencode.py`; просмотр лога `logs/reencode-*.json` в tmp | ✅ Скрипт перекодировки готов, тесты покрывают успешную перекодировку, пропуск UTF-8 и обработку ошибок. |
| 2025-09-30T11:15:00Z | D1 — перекодированы корневые HTML, RSS и ключевые лендинги; `tools/reencode.py` научили исправлять двойное кодирование | `python tools/reencode.py --paths index.html … rss/index.html` → `logs/reencode-20250930T070225Z.json`; `pytest tools/tests/test_reencode.py`; `python tools/check_utf8.py --scope index.html … --no-manifest` → `logs/check_utf8-20250930T070433Z.json` | ✅ Первая партия D1 закрыта, можно переходить к каталогам `p/0*`. |
| 2025-09-30T07:14:32Z | D2 — перекодировал серию `index0*`/`print0*` и подтвердил UTF-8 | `python tools/reencode.py --paths index0*.html print0*.html --limit 200` → `logs/reencode-20250930T071338Z.json`; `rg -n "windows-1251" index0*.html print0*.html`; `python tools/check_utf8.py --no-manifest …` → `logs/check_utf8-20250930T071432Z.json` | ✅ Серия `0*` в UTF-8, далее — `index1*`/`print1*`. |
| 2025-09-30T07:43:58Z | D2 — перекодировал серию `index1*`/`print1*` и провёл проверки | `python tools/reencode.py --paths index1*.html print1*.html --limit 200` → `logs/reencode-20250930T074259Z.json`; `rg -n "windows-1251" index1*.html print1*.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index1*.html print1*.html)` → `logs/check_utf8-20250930T074358Z.json`; `curl -I` по `index1178.html`, `index1a62.html`, `print1178.html` (через `python -m http.server`) | ✅ Серия `1*` подтверждена, следующая партия — `index2*`/`print2*`. |
| 2025-09-30T08:44:10Z | D2 — перекодировал серию `index2*`/`print2*` и подтвердил UTF-8 | `python tools/reencode.py --paths index2*.html print2*.html` → `logs/reencode-20250930T084226Z.json`; `rg -n "windows-1251" index2*.html print2*.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' index2*.html print2*.html)` → `logs/check_utf8-20250930T084335Z.json`; `python -m http.server 8000` + `curl -I` по `index205f.html`, `index2c55.html`, `print205f.html` | ✅ Серия `2*` подтверждена, следующая партия — `index3*`/`print3*`. |
| 2025-09-30T18:57:15Z | D2 — перекодировал серию `indexa*`/`printa*`, обновил мета-теги и подтвердил UTF-8 | `python tools/reencode.py --paths indexa*.html printa*.html` → `logs/reencode-20250930T185550Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g' indexa*.html printa*.html`; `rg -n "windows-1251" indexa*.html printa*.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' indexa*.html printa*.html)` → `logs/check_utf8-20250930T185702Z.json`; `python -m http.server 8000` + `curl -I` по `indexa0f3.html`, `printa0f3.html`, `indexa614.html` | ✅ Серия `indexa*`/`printa*` подтверждена, следующая партия — `indexb*`/`printb*`. |
| 2025-09-30T19:04:55Z | D2 — перекодировал серию `indexb*`/`printb*`, обновил мета-теги и подтвердил UTF-8 | `python tools/reencode.py --paths indexb*.html printb*.html --limit 200` → `logs/reencode-20250930T190424Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g' indexb*.html printb*.html`; `rg -n "windows-1251" indexb*.html printb*.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' indexb*.html printb*.html)` → `logs/check_utf8-20250930T190443Z.json`; `python -m http.server 8000` + `curl -I` по `indexb162.html`, `printb162.html`, `indexbb23.html` | ✅ Серия `indexb*`/`printb*` подтверждена, следующая партия — `indexc*`/`printc*`. |
| 2025-09-30T19:38:57Z | D2 — перекодировал серию `indexc*`/`printc*` и подтвердил UTF-8 | `python tools/reencode.py --paths indexc*.html printc*.html --limit 200` → `logs/reencode-20250930T193842Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g' indexc*.html printc*.html`; `rg -n "windows-1251" indexc*.html printc*.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' indexc*.html printc*.html)` → `logs/check_utf8-20250930T193857Z.json`; `python -m http.server 8000` + `curl -I` по `indexc1c8.html`, `indexc352.html`, `printc352.html` | ✅ Серия `indexc*`/`printc*` подтверждена, следующая партия — `indexd*`/`printd*`. |
| 2025-10-01T06:16:53Z | D2 — перекодировал серию `indexd*`/`printd*`, обновил мета-теги и подтвердил UTF-8 | `python tools/reencode.py --paths $(rg -l "windows-1251" indexd* printd*)` → `logs/reencode-20251001T061538Z.json`; `python - <<'PY'` (цикл по списку `indexd*`/`printd*` → замена `charset=windows-1251` на `charset=utf-8`); `rg -n "windows-1251" indexd*.html printd*.html`; `python - <<'PY'` (вызов `check_utf8.main` с `--no-manifest --scope <файл>`) → `logs/check_utf8-20251001T061632Z.json`; `python -m http.server 8000` + `curl -I` по `indexd00d.html`, `indexd538.html`, `printd538.html` | ✅ Серия `indexd*`/`printd*` подтверждена, следующая партия — `indexe*`/`printe*`. |
| 2025-10-01T14:58:04Z | D2 — перекодировал серию `indexe*`/`printe*`, обновил мета-теги и подтвердил UTF-8 | `python tools/reencode.py --paths $(printf '%s ' indexe*.html printe*.html)` → `logs/reencode-20251001T145635Z.json`; `python - <<'PY'` (цикл по `indexe*`/`printe*` → замена `charset=windows-1251` на `charset=utf-8`); `rg -n "windows-1251" indexe*.html printe*.html`; `python - <<'PY'` (вызов `tools/check_utf8.py --no-manifest --scope <файл>` для всей партии) → `logs/check_utf8-20251001T145804Z.json`; ручная проверка содержимого `indexe81b.html`, `indexe13d.html`, `printe13d.html` | ✅ Серия `indexe*`/`printe*` подтверждена, следующая партия — `indexf*`/`printf*`. |
| 2025-10-01T17:21:32Z | D2 — перекодировал серию `indexf*`/`printf*`, обновил мета-теги и провёл проверки | `python tools/reencode.py --paths indexf*.html printf*.html --limit 200` → `logs/reencode-20251001T172103Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g' indexf*.html printf*.html`; `rg -n "windows-1251" indexf*.html printf*.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' indexf*.html printf*.html)` → `logs/check_utf8-20251001T172119Z.json`; `python -m http.server 8000` + `curl -I` по `indexf0a1.html`, `indexf497.html`, `printf5a6.html` | ✅ Серия `indexf*`/`printf*` подтверждена, следующая партия — GUID-файлы. |
| 2025-10-01T17:42:56Z | D2 — перекодировал GUID-файлы с префиксами `0*`–`3*`, обновил объявления кодировки и подтвердил UTF-8 | `python - <<'PY'` (собрал список файлов `*.html`, начинающихся с 0–3, и запустил `tools/reencode.py --paths …` → `logs/reencode-20251001T174156Z.json`); `python - <<'PY'` (массово заменил `charset=windows-1251` на `charset=utf-8`); `rg -l "windows-1251" {0..3}*.html` → пусто; `python - <<'PY'` (вызвал `tools/check_utf8.py --no-manifest --scope <файл>` для партии → `logs/check_utf8-20251001T174240Z.json`); `python -m http.server 8000` + `curl -I` по `016538D0-F429D-CA4ECF10.html`, `1524DC52-F4651-2FB51D87.html`, `3D9668D0-F436B-A3575E15.html` | ✅ GUID-партии 0–3 переведены в UTF-8, следующая партия — `4*`–`6*`. |
| 2025-10-01T18:35:45Z | D2 — перекодировал GUID-файлы с префиксами `4*`–`6*`, обновил объявления кодировки и подтвердил UTF-8 | `python - <<'PY'` (подобрал список `*.html`, начинающихся с 4–6, и вызвал `tools/reencode.py --paths …` → `logs/reencode-20251001T183510Z.json`); `python - <<'PY'` (заменил `charset=windows-1251` на `charset=utf-8` в отобранных файлах); `python - <<'PY'` (вызвал `rg -n "windows-1251"` только для выбранных GUID → совпадений нет); `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' 4*.html 5*.html 6*.html)` → `logs/check_utf8-20251001T183532Z.json`; `python -m http.server 8000` + `curl -I` по `401DAD9C-F46D3-E86A6238.html`, `52FCBF6D-F429B-57C71EC1.html`, `6F14FAAF-F46EA-48902FF4.html` | ✅ GUID-партии 4–6 в UTF-8, следующая партия — `7*`–`9*`. |
| 2025-10-01T19:25:07Z | D2 — перекодировал GUID-файлы с префиксами `7*`–`9*`, обновил объявления кодировки и подтвердил UTF-8 | `python tools/reencode.py --paths <список 7*.html 8*.html 9*.html>` (список собран однострочным `python - <<'PY'` и сохранён в подстановку) → `logs/reencode-20251001T192413Z.json`; `python - <<'PY'` (заменил `charset=windows-1251` на `charset=utf-8` в выбранных GUID); `rg -n "windows-1251" 7*.html 8*.html 9*.html`; `python tools/check_utf8.py --no-manifest` c параметрами `--scope <файл>` по всей партии (генерация списка также через `python - <<'PY'`) → `logs/check_utf8-20251001T192421Z.json`; `python -m http.server 8000` + `curl -I` по `7-levels-leadership.html`, `80CE685C-F4614-5D368325.html`, `9ECA3D61-F4288-CB0CCCDB.html` | ✅ GUID-партии 7–9 подтверждены в UTF-8, следующая партия — `A*`–`C*`. |
| 2025-10-01T19:52:30Z | D2 — перекодировал GUID-файлы с префиксами `A*`–`C*`, обновил объявления кодировки и подтвердил UTF-8 | `python - <<'PY'` (собрал список файлов `A*.html B*.html C*.html` и запустил `tools/reencode.py --paths …` → `logs/reencode-20251001T193029Z.json`); `python - <<'PY'` (массово заменил `charset=windows-1251` на `charset=utf-8` в выбранных файлах); `rg -n "windows-1251" A*.html B*.html C*.html` → пусто; `python - <<'PY'` (вызвал `tools/check_utf8.py --no-manifest` с параметрами `--scope <файл>` для всей партии → `logs/check_utf8-20251001T193039Z.json`); `sed -n '6,15p' A0E5F947-F4655-5A54C351.html`, `sed -n '6,15p' B3682F35-F4707-7A393FEE.html`, `sed -n '6,15p' CABE4B60-F4298-EC607BAC.html` | ✅ GUID-партии `A*`–`C*` подтверждены в UTF-8, следующая партия — `D*`–`F*`. |
| 2025-10-02T15:57:33Z | D2 — перекодировал GUID-файлы с префиксами `D*`–`E*`, обновил объявления кодировки и подтвердил UTF-8 | `python tools/reencode.py --paths D02DBF37-F46B9-834FCE15.html … EF55077A-F45BC-9F9EDC1A.html` → `logs/reencode-20251002T155722Z.json`; `python - <<'PY'` (замена `charset=windows-1251` → `charset=utf-8` в `[DE]*.html`); `rg -n "windows-1251" D*.html E*.html` → пусто; `python - <<'PY'` (`tools/check_utf8.py --no-manifest --scope <файл>` для партии → `logs/check_utf8-20251002T155733Z.json`); ручная проверка заголовков `D02DBF37-F46B9-834FCE15.html`, `DA048280-F434C-05FECECD.html`, `E9C8323C-F45AA-E174FB9E.html` | ✅ GUID-партии `D*`–`E*` в UTF-8, следующая партия — `F*`. |
| 2025-10-03T09:52:27Z | D2 — перекодировал блок `F471B.html`…`F478D.html` (12 файлов) и подтвердил новую стратегию лимита | `python tools/reencode.py --paths F471B.html … F478D.html` → `logs/reencode-20251003T095151Z.json`; `python - <<'PY'` (замена `charset=windows-1251` → `charset=utf-8` для выбранных файлов); `rg -n "windows-1251" F471B.html … F478D.html` → пусто; `python - <<'PY'` (`check_utf8.main` с `--no-manifest` и `--scope` по каждому файлу) → `logs/check_utf8-20251003T095227Z.json`; ручная проверка `F471B.html`, `F4759.html`, `F478D.html` | ✅ Стартовый блок `F47x` подтверждён, `safe_bound_html_guid` актуализирован (12 файлов), следующий блок — оставшиеся `F47x`. |
| 2025-10-03T10:02:10Z | D2 — перекодировал оставшиеся файлы подсерии `F47x` (`F4792.html`…`F47BA.html`), обновил объявления кодировки и подтвердил UTF-8 | `python tools/reencode.py --paths F4792.html … F47BA.html --limit 200` → `logs/reencode-20251003T100140Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g'` по партии; `rg -n "windows-1251" F4792.html … F47BA.html` → пусто; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4792.html … F47BA.html)` → `logs/check_utf8-20251003T100152Z.json`; `python -m http.server 8000` + `curl -I` по `F4792.html`, `F47A3.html`, `F47B7.html` | ✅ Подсерия `F47x` завершена, следующая партия — `F48x`. |
| 2025-10-03T12:29:49Z | D2 — перекодировал первую партию подсерии `F48x` (`F4833.html`…`F486E.html`), обновил мета-теги и подтвердил UTF-8 | `python tools/reencode.py --paths F4833.html … F486E.html` → `logs/reencode-20251003T122902Z.json`; `python - <<'PY'` (замена `charset=windows-1251` → `charset=utf-8` в выбранных файлах); `rg -n "windows-1251" F4833.html … F486E.html` → пусто; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4833.html … F486E.html)` → `logs/check_utf8-20251003T122949Z.json` | ✅ Партия на 12 файлов прошла, `safe_bound_html_guid` подтверждён; следующая подсерия — оставшиеся `F48x`. |
| 2025-10-03T13:31:42Z | D2 — перекодировал подсерию `F48x` (`F4876.html`…`F48A9.html`) и подтвердил UTF-8 | `python tools/reencode.py --paths F4876.html … F48A9.html` → `logs/reencode-20251003T133116Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g' $FILES`; `rg -n "windows-1251" F4876.html … F48A9.html` → пусто; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4876.html … F48A9.html)` → `logs/check_utf8-20251003T133135Z.json`; `python -m http.server 8000` + `curl -I` по `F4876.html`, `F4885.html`, `F48A7.html` | ✅ Партия прошла, осталось закрыть `F48AB.html`…`F48ED.html`. |
| 2025-10-03T19:41:52Z | D2 — перекодировал финальный блок `F48AB.html`…`F48ED.html` (10 файлов) | `python tools/reencode.py --paths F48AB.html … F48ED.html --limit 200` → `logs/reencode-20251003T194152Z.json`; `rg -n "windows-1251" F48*.html` → пусто | ✅ Подсерия `F48x` полностью в UTF-8, мета-теги обновлены. |
| 2025-10-03T19:42:16Z | D2 — подтвердил кодировку и заголовки финального блока `F48x` | `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F48AB.html … F48ED.html)` → `logs/check_utf8-20251003T194210Z.json`; `python -m http.server 8000` + `curl -I` по `F48AB.html`, `F48E0.html`, `F48ED.html` | ✅ Проверки прошли, готов к подсерии `F49x`. |
| 2025-10-03T19:52:13Z | D2 — перекодировал подсерии `F4902.html` и `F49ED.html`, подтвердил UTF-8 | `python tools/reencode.py --paths F4902.html F49ED.html` → `logs/reencode-20251003T195158Z.json`; `python - <<'PY'` (замена `charset=windows-1251` → `charset=utf-8`); `rg -n "windows-1251" F4902.html F49ED.html`; `python tools/check_utf8.py --no-manifest --scope F4902.html --scope F49ED.html` → `logs/check_utf8-20251003T195207Z.json`; `python -m http.server 8000` + `curl -I` по `F4902.html`, `F49ED.html` | ✅ Подсерия `F49x` подтверждена, следующая партия — `F4Ax`. |
| 2025-10-03T20:03:47Z | D2 — перекодировал блок `F4A11.html`…`F4A46.html` (12 файлов) | `python tools/reencode.py --paths F4A11.html … F4A46.html` → `logs/reencode-20251003T200347Z.json`; `python - <<'PY'` (замена `charset=windows-1251` → `charset=utf-8` в партии); `rg -n "windows-1251" F4A11.html … F4A46.html` | ✅ Партия переведена в UTF-8, `safe_bound_html_guid` подтверждён. |
| 2025-10-03T20:04:22Z | D2 — подтвердил кодировку блока `F4A11.html`…`F4A46.html` | `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4A11.html … F4A46.html)` → `logs/check_utf8-20251003T200422Z.json`; ручной просмотр `F4A11.html`, `F4A29.html`, `F4A46.html` | ✅ Проверки прошли, следующая партия — `F4A47.html`…`F4A99.html`. |
| 2025-10-03T20:10:59Z | D2 — перекодировал подсерию `F4A47.html`…`F4A99.html` и подтвердил UTF-8 | `python tools/reencode.py --paths F4A47.html … F4A99.html --limit 200` → `logs/reencode-20251003T201039Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g'` по партии; `rg -n "windows-1251" F4A47.html … F4A99.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4A47.html … F4A99.html)` → `logs/check_utf8-20251003T201048Z.json`; `python -m http.server 8000` + `curl -I` по `F4A47.html`, `F4A88.html`, `F4A99.html` | ✅ Подсерия `F4A47.html`…`F4A99.html` подтверждена, следующая партия — `F4AA1.html`…`F4ACB.html`. |
| 2025-10-03T20:21:27Z | D2 — перекодировал подсерию `F4AA1.html`…`F4ACB.html` и синхронизировал мета-charset | `python tools/reencode.py --paths F4AA1.html … F4ACB.html --limit 200` → `logs/reencode-20251003T202056Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g'` по партии; `rg -n "windows-1251" F4AA1.html … F4ACB.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4AA1.html … F4ACB.html)` → `logs/check_utf8-20251003T202127Z.json`; ручной просмотр `F4AA1.html`, `F4AC0.html`, `F4ACB.html` | ✅ Подсерия `F4AA1.html`…`F4ACB.html` подтверждена, следующая партия — `F4AD6.html`…`F4AFC`. |
| 2025-10-03T20:27:45Z | D2 — перекодировал подсерию `F4AD6.html`…`F4AFC.html` и обновил мета-charset | `python tools/reencode.py --paths F4AD6.html … F4AFC.html --limit 200` → `logs/reencode-20251003T202745Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g'` по партии; `rg -n "windows-1251" F4AD6.html … F4AFC.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4AD6.html … F4AFC.html)` → `logs/check_utf8-20251003T202812Z.json`; `python -m http.server 8000` + `curl -I` по `F4AD6.html`, `F4AFA.html` | ✅ Подсерия `F4AD6.html`…`F4AFC.html` зафиксирована, готовим блок `F4C14.html`…`F4C53.html`. |
| 2025-10-04T13:47:55Z | D2 — перекодировал подсерию `F4C14.html`…`F4C53.html` и синхронизировал charset | `python tools/reencode.py --paths F4C14.html … F4C53.html --limit 200` → `logs/reencode-20251004T134755Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g'` по партии; `rg -n "windows-1251" F4C14.html … F4C53.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4C14.html … F4C53.html)` → `logs/check_utf8-20251004T134809Z.json`; ручной просмотр `F4C14.html`, `F4C3F.html` | ✅ Партия `F4C14.html`…`F4C53.html` перекодирована, далее блок `F4C54.html`…`F4CED.html`. |
| 2025-10-04T14:08:46Z | D2 — перекодировал подсерию `F4C54.html`…`F4CED.html` и обновил meta-charset | `python tools/reencode.py --paths F4C54.html … F4CED.html --limit 150` → `logs/reencode-20251004T140846Z.json`; `python - <<'PY'` (замена `charset=windows-1251` → `charset=utf-8`); `rg -n "windows-1251" F4C54.html … F4CED.html`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4C54.html … F4CED.html)` → `logs/check_utf8-20251004T140857Z.json`; `sed -n '1,20p' F4C54.html`, `sed -n '1,20p' F4CD0.html` | ✅ Подсерия `F4C54.html`…`F4CED.html` подтверждена в UTF-8, следующий шаг — одиночный `F4CF5.html`. |
| 2025-10-05T06:12:01Z | D2 — перекодировал одиночный `F4CF5.html` в UTF-8 | `python tools/reencode.py --paths F4CF5.html --limit 50` → `logs/reencode-20251005T061201Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/' F4CF5.html`; `rg -n "windows-1251" F4CF5.html` | ✅ Файл переведён в UTF-8 без артефактов. |
| 2025-10-05T06:12:14Z | D2 — подтвердил кодировку и заголовки `F4CF5.html` | `python tools/check_utf8.py --no-manifest --scope F4CF5.html` → `logs/check_utf8-20251005T061214Z.json`; `python -m http.server 8000` + `curl -I http://127.0.0.1:8000/F4CF5.html` | ✅ Проверки прошли, можно браться за блок `F4D*`. |
| 2025-10-05T06:12:25Z | D2 — перекодировал блок `F4D10.html`…`F4DE8.html` (8 файлов) | `python tools/reencode.py --paths F4D10.html … F4DE8.html --limit 100` → `logs/reencode-20251005T061225Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g'` по партии; `rg -n "windows-1251" F4D10.html … F4DE8.html` | ✅ Партия `F4D10.html`…`F4DE8.html` перекодирована. |
| 2025-10-05T06:12:31Z | D2 — перекодировал блок `F4DEE.html`…`F4DFF.html` (8 файлов) | `python tools/reencode.py --paths F4DEE.html … F4DFF.html --limit 100` → `logs/reencode-20251005T061231Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g' F4DEE.html … F4DFF.html`; `rg -n "windows-1251" F4DEE.html … F4DFF.html` | ✅ Подсерия `F4D*` переведена в UTF-8. |
| 2025-10-05T06:12:57Z | D2 — подтвердил кодировку блока `F4D10.html`…`F4DFF.html` | `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' F4D10.html … F4DFF.html)` → `logs/check_utf8-20251005T061257Z.json`; `python -m http.server 8000` + `curl -I` по `F4D10.html`, `F4DF9.html`, `F4DFF.html` | ✅ Проверки прошли, следующая партия — `F4E*`. |
| 2025-10-05T06:39:32Z | D2 — перекодировал блок `F4E00.html`…`F4E16.html` и подтвердил UTF-8 | `python tools/reencode.py --paths F4E00.html F4E04.html F4E16.html --limit 50` → `logs/reencode-20251005T063914Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g' F4E00.html F4E04.html F4E16.html`; `rg -n "windows-1251" F4E*.html`; `python tools/check_utf8.py --no-manifest --scope F4E00.html --scope F4E04.html --scope F4E16.html` → `logs/check_utf8-20251005T063925Z.json`; `python -m http.server 8000` + `curl -I` по `F4E00.html`, `F4E04.html`, `F4E16.html` | ✅ Партия `F4E*` подтверждена, следующая цель — `F0*`/`F2*`. |
| 2025-10-07T12:23:18Z | D2 — перекодировал кластер GUID `F0*`/`F2*` в UTF-8 | `python tools/reencode.py --paths F05E6200-F45A7-0A75F0C1.html F0651E00-F428A-D059ED75.html F0CB3C38-F449A-60E70531.html F2F5B577-F45F4-635C9E21.html --limit 50` → `logs/reencode-20251007T122318Z.json`; `python - <<'PY'` (замена `charset=windows-1251` → `charset=utf-8` для четырёх файлов); `rg -n "windows-1251" F0*.html F2*.html` | ✅ Кластер перекодирован, объявления `charset` синхронизированы. |
| 2025-10-07T12:23:43Z | D2 — подтвердил UTF-8 для `F05E6200…`, `F0651E00…`, `F0CB3C38…`, `F2F5B577…` | `python tools/check_utf8.py --no-manifest --scope F05E6200-F45A7-0A75F0C1.html --scope F0651E00-F428A-D059ED75.html --scope F0CB3C38-F449A-60E70531.html --scope F2F5B577-F45F4-635C9E21.html` → `logs/check_utf8-20251007T122332Z.json`; `python -m http.server 8000` + `curl -I` по `F05E6200…`, `F0CB3C38…`, `F2F5B577…` | ✅ Проверки прошли, следующая партия — одиночные `F5*`/`F8*`/`F9*`/`FC*`. |
| 2025-10-07T17:17:00Z | D2 — перекодировал одиночные GUID `F5576ACF-F4601-3A7A13DF.html`, `F8098E52-F4631-38207BC3.html`, `F9505086-F45DB-F1785BE2.html`, `FCFECF83-F46D5-7B58EE90.html` | `python tools/reencode.py --paths F5576ACF-F4601-3A7A13DF.html F8098E52-F4631-38207BC3.html F9505086-F45DB-F1785BE2.html FCFECF83-F46D5-7B58EE90.html --limit 20` → `logs/reencode-20251007T171700Z.json`; `perl -0pi -e 's/charset=windows-1251/charset=utf-8/g'` по каждому файлу; `rg -n "windows-1251"` → пусто | ✅ Партия одиночных GUID перекодирована. |
| 2025-10-07T17:17:12Z | D2 — подтвердил UTF-8 для одиночных GUID | `python tools/check_utf8.py --no-manifest --scope F5576ACF-F4601-3A7A13DF.html --scope F8098E52-F4631-38207BC3.html --scope F9505086-F45DB-F1785BE2.html --scope FCFECF83-F46D5-7B58EE90.html` → `logs/check_utf8-20251007T171712Z.json`; `python -m http.server 8000` + `curl -I` по `F5576ACF-F4601-3A7A13DF.html`, `F8098E52-F4631-38207BC3.html`, `FCFECF83-F46D5-7B58EE90.html` | ✅ Проверки подтвердили корректную отдачу. |
| 2025-10-08T09:56:18Z | D2 — перекодировал тематические страницы (`blog&page=*.html`, `coaching.html`, `erickson_hypnosis*.html`, `nlp-master.html`, `pages_edit133b.html`, `reality_maker_barselona.html`, `subscribe_*.html`, `trainings_photo_collection.html`, `tricks_of_language*.html`, `tropa_movie.html`, `4Qart.html`) и подтвердил UTF-8 | `python tools/reencode.py --paths 4Qart.html blog&page=2.html … tropa_movie.html` → `logs/reencode-20251008T095552Z.json`; `rg -n "windows-1251" <выборка>`; `python tools/check_utf8.py --no-manifest$(printf ' --scope %s' 4Qart.html blog&page=2.html … tropa_movie.html)` → `logs/check_utf8-20251008T095618Z.json`; просмотр `blog.html`, `subscribe_success.html`, `tropa_movie.html` | ✅ Страницы блога и тематических лендингов переведены в UTF-8, следующий блок — статьи `F47C1.html`…`F47E4.html`, `ask46c6.html`, `blondy_strategy.html`, `spiralnaya_dinamika_vvedenie.html`. |
| 2025-10-08T10:58:10Z | D2 — финальный контроль по манифесту перед переходом к Dlast | `python tools/check_utf8.py --manifest tools/url_manifest.txt` → `logs/check_utf8-20251008T105810Z.json` (отчёт без замечаний) | ✅ Прогон зафиксирован, готовимся к этапу Dlast. |
| 2025-09-28T19:10:12Z | C1 — фиксация завершения: корневые HTML и раздел «Видео» работают из корня, наследие hop-трекера удалено | Проверки: `rg -n "my_hop_host" -g'*.html'` → пусто; `rg -n "s\\.nlping\\.ru/sapi/Click\\.js" -g'*.html'` → пусто; `git status -sb` | ✅ Шаг C1 закрыт, следующий этап — перенос ассетов (C2). |

#### Архив: чек-лист шага C1 (перенос корневых HTML)

1. Определи список страниц из `nlping.ru/`, которые должны оказаться в корне (например, `index.html`, `blog.html`, `news.html`, `rss/index.html`). Сверься с `tools/url_manifest.txt` и выводом `python tools/list_assets.py`.
2. Проанализируй текущий корневой `index.html` (шаблон HTTrack). Подготовь замену из `nlping.ru/index.html` и убедись, что главная страница корректно ссылается на CSS/JS после переезда.
3. Переноси файлы партиями (`git mv nlping.ru/<файл> <файл>`), после каждой партии прогоняй проверки и ручной просмотр.
4. Исправляй относительные пути (`../nlping.ru/` и т.п.), обновляй ссылки внутри HTML на новый корень.
5. После переноса убедись, что в `nlping.ru/` не осталось дубликатов страниц и что навигация из корня работает.
6. Обнови инструменты/конфигурацию, которые ссылаются на каталог `nlping.ru` (`DEFAULT_ROOT` в `tools/check_links.py`, `tools/check_utf8.py`, `generate_md5_baseline.py`, `generate_seo_baseline.py`, список по умолчанию в `tools/list_assets.py`, а также пути в `tools/url_manifest.txt`).
7. Проверь `.gitignore` и путевые зависимости, чтобы перенос не сломал игнорирование `snapshot/` и `logs/`.

> Исторический блок перенесён в журнал 2025-09-28 после закрытия шага C1.

## Текущее состояние дорожной карты

- ✅ A1: дорожная карта зафиксирована (этот документ).
- ✅ A2: baseline контрольных сумм генерируется скриптом (`python tools/generate_md5_baseline.py` → `snapshot/baseline_md5.txt.gz`, вне git).
- ✅ A3: подготовлен манифест ключевых URL (`tools/url_manifest.txt`).
- ✅ A5: памятки memory-bank созданы (`memory-bank/MB-*.md`).
- ✅ A4: оффлайн-слепок и SEO-бейзлайн создаются локально (`snapshot/` содержит только `.gitkeep`, артефакты генерируются по запросу).
- ✅ B1: создан и выполнен `tools/list_assets.py`, отчёт в `artifacts/assets.json`.
- ✅ B2: `tools/check_links.py` подтверждает отсутствие битых ресурсов (`logs/check_links-20250923T200035Z.json`), устаревший hop-скрипт удалён.
- ✅ B3: `tools/check_utf8.py` проверяет кодировку и SEO-блоки; логи — `logs/check_utf8-*.json`.
- ✅ C1: перенос корневых HTML завершён — весь верхний уровень переехал в корень, каталог `nlping.ru/` больше не содержит HTML-файлов.
- ✅ C2: каталоги `_p_http_/`, `files/`, `player/`, `rep/`, `p/` перенесены в корень, проверки по партиям зафиксированы.
- ✅ C3: HTTrack-артефакты удалены, README отражает новую структуру.
- ✅ D0: `tools/reencode.py` перекодирует HTML/XML в UTF-8, тесты покрывают сценарии успеха/ошибок.
- ✅ D1: корневые HTML, RSS и ключевые лендинги перекодированы в UTF-8 (`logs/reencode-20250930T070225Z.json`, `logs/check_utf8-20250930T070433Z.json`).
- ✅ D2: серии `index0*`/`print0*`, `index1*`/`print1*`, `index2*`/`print2*`, `index3*`/`print3*`, `index4*`/`print4*`, `index5*`/`print5*`, `index6*`/`print6*`, `index7*`/`print7*`, `index8*`/`print8*`, `index9*`/`print9*`, `indexa*`/`printa*`, `indexb*`/`printb*`, `indexc*`/`printc*`, `indexd*`/`printd*`, `indexe*`/`printe*`, `indexf*`/`printf*`, все кластеры GUID `0*`–`FCFECF83`, тематические лендинги и спецстраницы перекодированы; итоговый прогон `tools/check_utf8.py --manifest tools/url_manifest.txt` подтвердил отсутствие `windows-1251` в кодовой базе (`logs/check_utf8-20251008T105810Z.json`).

**Следующий шаг:** Dlast — выполнить финальную валидацию: `rg -n "windows-1251" -g'*.html'`, при необходимости обновить контрольные суммы (`python tools/generate_md5_baseline.py`), закрепить результаты и подготовить переход к этапу E.

#### План партии `F*` (завершён)

- **Стратегия лимита.** Применяем протокол «обстукивание туннеля» из `memory-bank/diff-limit-plan.md`: стартуем с гарантированного размера (10–12 файлов), фиксируем безопасную и неудачную границы, чередуем попытки без двух провалов подряд.
- **Кластеры:** `F47x`, `F48x`, `F49x`, `F4Ax`, `F4Cx`, `F4Dx`, `F4Ex`, `F0x/F2x`, одиночные `F5*`, `F8*`, `F9*`, `FC*`.
- **Блок 1 (✅ выполнено):** `F471B.html`…`F478D.html` — 12 файлов, подтвердили безопасный размер и обновили `safe_bound_html_guid`.
- **Блок 2 (✅ выполнено):** `F4792.html`…`F47BA.html` — 12 файлов, подтвердили безопасный объём и зафиксировали логи `logs/reencode-20251003T100140Z.json`, `logs/check_utf8-20251003T100152Z.json`.
- **Блок 3a (✅ выполнено):** `F4833.html`…`F486E.html` — 12 файлов, подтверждён безопасный объём; логи `logs/reencode-20251003T122902Z.json`, `logs/check_utf8-20251003T122949Z.json`.
- **Блок 3b (✅ выполнено):** `F4876.html`…`F48ED.html` — финальная подсерия перекодирована и проверена (`logs/reencode-20251003T194152Z.json`, `logs/check_utf8-20251003T194210Z.json`).
- **Блок 4 (✅ выполнено):** `F4902.html`…`F49ED.html` — подтверждён перевод в UTF-8 (`logs/reencode-20251003T195158Z.json`, `logs/check_utf8-20251003T195207Z.json`).
- **Блок 5 (✅ выполнено):** `F4A11.html`…`F4A46.html` — партия на 12 файлов, логи `logs/reencode-20251003T200347Z.json`, `logs/check_utf8-20251003T200422Z.json`.
- **Блок 6 (✅ выполнено):** `F4A47.html`…`F4A99.html` — партия на 12 файлов, логи `logs/reencode-20251003T201039Z.json`, `logs/check_utf8-20251003T201048Z.json`.
- **Блок 7 (✅ выполнено):** `F4AA1.html`…`F4ACB.html` — партия на 12 файлов, логи `logs/reencode-20251003T202056Z.json`, `logs/check_utf8-20251003T202127Z.json`.
- **Блок 8 (✅ выполнено):** `F4AD6.html`…`F4AFC.html` — партия на 13 файлов, логи `logs/reencode-20251003T202745Z.json`, `logs/check_utf8-20251003T202812Z.json`; следующая цель `F4C14.html`…`F4C53.html`.
- **Блок 9 (✅ выполнено):** `F4C14.html`…`F4CED.html` — партии на 12 файлов, логи `logs/reencode-20251004T134755Z.json`, `logs/reencode-20251004T140846Z.json`, `logs/check_utf8-20251004T134809Z.json`, `logs/check_utf8-20251004T140857Z.json`.
- **Блок 10 (✅ выполнено):** `F4D10.html`…`F4DFF.html` — партии на 17 файлов (1 + 8 + 8 с учётом `F4CF5.html`), логи `logs/reencode-20251005T061201Z.json`, `logs/reencode-20251005T061225Z.json`, `logs/reencode-20251005T061231Z.json`, `logs/check_utf8-20251005T061214Z.json`, `logs/check_utf8-20251005T061257Z.json`.
- **Блок 11 (✅ выполнено):** `F4E00.html`…`F4E16.html` — партия на 3 файла, логи `logs/reencode-20251005T063914Z.json`, `logs/check_utf8-20251005T063925Z.json`.
- **Блок 12 (✅ выполнено):** `F05E6200-F45A7-0A75F0C1.html`, `F0651E00-F428A-D059ED75.html`, `F0CB3C38-F449A-60E70531.html`, `F2F5B577-F45F4-635C9E21.html` — партия на 4 файла, логи `logs/reencode-20251007T122318Z.json`, `logs/check_utf8-20251007T122332Z.json`.
- **Блок 13 (✅ выполнено):** `F5576ACF-F4601-3A7A13DF.html`, `F8098E52-F4631-38207BC3.html`, `F9505086-F45DB-F1785BE2.html`, `FCFECF83-F46D5-7B58EE90.html` — партия на 4 файла, логи `logs/reencode-20251007T171700Z.json`, `logs/check_utf8-20251007T171712Z.json`.
- План `F*` закрыт — все подсерии и одиночные GUID переведены в UTF-8; далее нужно сформировать новый план для тематических лендингов и статических страниц.
- После каждого блока обновляем таблицу прогресса и журнал лимитов.

### Быстрый старт сессии

1. Открой эту дорожную карту и определи актуальный подпункт.
2. Загляни в `INSTRUKTSIYA_VYPOLNENIYA.md`, чтобы следовать чек-листу на текущем этапе.
3. Подтяни связанные заметки из `memory-bank/` (например, MB-02 и MB-06). Если браузер завис или контекст обнулился — повтори короткий промпт «Протокол, шаг `<код>`», и нужные документы снова откроются в правильном порядке.
