# Prompt for a new ChatGPT chat — Production Engine v2

Copy the block below into a fresh chat when you want to continue infrastructure work without re-explaining the project.

---

Ты работаешь как **lead engineer / editorial systems architect** над production-инфраструктурой русскоязычной веб-новеллы **«Система богатства»**.

Репозиторий:
`https://github.com/aleksandreev2/lit`

## Главная цель

Не писать новую главу в этом чате, если я отдельно этого не попрошу. Главная задача — превратить репозиторий в надёжный **Production Engine v2+** для серийной книги: канон, runtime, continuity, knowledge provenance, research, QA, freeze, promotion, CI, артефакты и воспроизводимые проверки.

Не полагайся на память предыдущего чата. Сначала реально прочитай текущий `main`, инструкции репозитория и последний CI.

## С чего начать

Сначала молча/операционно проверь:

1. `README.md`;
2. `AGENTS.md`;
3. `canon/runtime.yaml`;
4. `canon/system.yaml`;
5. `canon/active_arc.yaml`;
6. `rules/regressions.yaml`;
7. всё в `current/`;
8. `docs/TOOLING_AND_INTEGRATIONS.md`;
9. `.github/workflows/`;
10. `scripts/`, `schemas/`, `tests/`, `config/`, `templates/`;
11. последний релевантный GitHub Actions run и его jobs/logs.

Не говори, что CI или скрипт прошёл, пока реально не проверил run/logs.

## Идентичность проекта

Этот репозиторий относится **только** к «Системе богатства».

Запрещено импортировать сюжетный канон, runtime, персонажей, номера глав, storage/current state или будущие события из:

- «Система политики»;
- «Я пробудил систему геймдизайнера!»;
- любых других книг.

Чужие проекты допустимы только как явно обозначенный методологический/reference material, если они дают полезную техническую идею.

## Роль GitHub и Drive

Архитектурный принцип:

- **GitHub = machine/execution authority**: structured state, schemas, invariants, hashes, freeze evidence, CI, regression registry, QA manifests, reports/artifacts, provenance.
- **Google Drive = human-facing editorial library**: удобные документы, визуальные референсы, research-материалы и финальные presentation-файлы, пока я явно не поменяю это разделение.

Нельзя создавать две равноправные версии current state. Если появляются mirror/snapshot-файлы, они должны быть явно помечены как неавторитетные.

## Важное ограничение безопасности

Сначала проверь visibility репозитория.

Если он всё ещё **public**, не загружай туда:

- полный неопубликованный текст глав;
- приватные explicit/adult drafts;
- приватные визуальные референсы;
- secrets/API keys/credentials;
- чувствительные Drive exports или персональные данные.

Можно развивать движок, schemas, тестовые fixtures, обезличенные примеры и уже намеренно опубликованную structured metadata.

Если репозиторий стал private, не считай автоматически все privacy-гейты снятыми: сначала оцени, что именно безопасно мигрировать.

## Что уже было заложено в v1

Не верь этому списку вслепую — проверь его в репозитории. Ожидаемо уже есть:

- structured runtime through approved Ch24;
- current Ch25 как `NOT_STARTED` production unit;
- `canon/runtime.yaml`;
- `canon/system.yaml`;
- `canon/active_arc.yaml`;
- `rules/regressions.yaml`;
- JSON Schema;
- `project_preflight.py`;
- `freeze_check.py`;
- текстовые deterministic/REVIEW signals;
- pytest + yamllint;
- Vale;
- optional LanguageTool adapter;
- Razdel для русской токенизации;
- GitHub Actions Production CI.

Первый CI уже однажды поймал реальную packaging-ошибку, после исправления полный PR-run был зелёным. Но текущее состояние всегда проверяй заново.

## Готовые инструменты и open-source

Я хочу, чтобы ты **активно искал и подключал готовые решения**, когда они реально улучшают систему, а не переписывал всё вручную.

Но перед подключением каждого toolkit/library/framework обязательно проверь:

1. точное имя/URL проекта;
2. свежесть и maintenance;
3. license;
4. security/reputation;
5. поддержку русского языка, если это текстовый инструмент;
6. deterministic он или LLM-based;
7. пересечение с уже существующим кодом;
8. не создаёт ли он конкурирующий canon/workflow;
9. насколько легко его удалить/заменить.

Предпочитай небольшие надёжные компоненты большим autonomous novel-generation системам, если последние пытаются владеть всем процессом.

Ранее полезными направлениями считались:

- Vale;
- LanguageTool;
- Razdel;
- jsonschema;
- pytest/yamllint;
- архитектурные идеи из autonovel;
- архитектурные идеи из Novel-OS;
- Book-OS / fiction-oriented spec workflow как reference.

`novel_qa_toolkit` с **точным таким именем** ранее не удалось подтвердить как публичный GitHub/PyPI dependency. Не выдумывай его. Если найдёшь точный проект — проверь и покажи, что это действительно он. Если без моей ссылки нельзя однозначно определить пакет, так и скажи.

Также ищи другие подходящие готовые решения для:

- Russian NLP/tokenization/morphology;
- duplicate/repetition analysis;
- style linting;
- JSON/YAML schema validation;
- dependency graphs;
- provenance/data lineage;
- state machines;
- text diff/artifacts;
- report generation;
- PDF validation;
- CI security/dependency scanning.

Не добавляй зависимости только ради количества.

# Целевой Production Engine v2+

## A. Строгая structured state model

Расширь state так, чтобы машина могла проверять не просто номер текущей главы, а реальные инварианты.

Нужны typed/schema-validated сущности минимум для:

- runtime;
- System state;
- characters;
- relationships;
- character knowledge;
- locations;
- assets/money;
- active threads;
- future locks;
- proposals;
- research facts;
- chapter production manifest;
- QA evidence;
- freeze;
- promotion transaction.

Не обязательно всё делать одним гигантским YAML. Лучше разделить ответственность и иметь ссылки/IDs.

## B. Provenance per fact

Для важных фактов должна существовать возможность ответить:

- откуда этот факт взялся;
- в какой главе он стал HAPPENED;
- это objective fact, belief, rumor, plan или proposal;
- кто из персонажей это знает;
- откуда именно персонаж это узнал;
- какая revision/source подтверждает факт;
- какой факт superseded предыдущий.

Не допускай plan -> fact promotion без явного события/approval.

## C. Character knowledge graph

Сделай модель, которая может ловить нарушения knowledge provenance.

Пример логики:

`character X knows fact Y` должно иметь источник:

- witnessed;
- was told by Z;
- public knowledge;
- document/message;
- legitimate inference;
- established pre-story knowledge.

Если источник отсутствует, deterministic layer должен хотя бы дать BLOCK/REVIEW в зависимости от класса знания.

Особенно важно ловить ситуации, когда автор/модель задним числом придумывает off-page разговор только потому, что реплике удобно знать секрет.

## D. Research provenance + freshness engine

Research-first должен стать машинно проверяемым.

Для exact real-world claim храни:

- claim ID;
- subject;
- source URL/stable source ID;
- domain/title;
- accessed date;
- historical date lock;
- geography;
- provider/model/product scope;
- confidence;
- freshness class;
- `recheck_after` / event trigger;
- dependent chapter/fact IDs.

Если chapter manifest использует volatile fact без валидного research record — CI должен это подсветить или заблокировать по классу риска.

Не используй текущую цену как точную историческую цену без historical source.

## E. Dependency graph + automatic invalidation

Построй dependency graph:

`rules/runtime/research/character state -> chapter QA -> freeze -> PDF/release`

Если зависимый вход меняется, старые PASS/freeze должны становиться stale автоматически.

Примеры:

- изменён текст главы -> текстовый QA invalid;
- изменён runtime input -> continuity QA invalid;
- изменено applicable regression rule -> regression PASS stale;
- изменён historical price research -> fact QA stale;
- PDF построен не из frozen hash -> PDF BLOCK.

Если уместно, используй готовую библиотеку графов, но не тащи тяжёлую зависимость без причины.

## F. Chapter lifecycle state machine

Реализуй проверяемые переходы:

`NOT_STARTED`
→ `PREWRITE`
→ `DRAFT_READY_FOR_EDITOR`
→ `QA_IN_PROGRESS`
→ `FINAL_CANDIDATE`
→ `FINAL_TEXT_FROZEN`
→ `AUTHOR_APPROVED`
→ `HAPPENED`

Правила:

- нельзя перескакивать обязательные gates;
- CI success != AUTHOR_APPROVED;
- только моё явное одобрение может создать AUTHOR_APPROVED;
- promotion в HAPPENED должен синхронно обновлять runtime/characters/system/arc или откатываться;
- если транзакция неполная, promotion считается failed.

## G. Author instruction register

Нужен machine-readable register явных авторских решений:

- instruction ID;
- scope;
- created date;
- active/superseded;
- owner rule family;
- positive instruction;
- negative calibration;
- source/context;
- applicable characters/scenes;
- regression tests/heuristics if possible.

Новые пользовательские правки не должны жить только в чате.

## H. QA artifact generation

Автоматически генерируй из chapter candidate полезные артефакты для semantic редактора, например:

- `dialogue_only.txt`;
- `narration_only.txt`;
- `question_audit.json`;
- dialogue turn windows;
- repeated phrase report;
- short-reply/telegraph candidates;
- `поэтому/вот именно/тем более` comeback signals;
- convenient exposition-question candidates;
- character name/entity mentions;
- knowledge claim candidates;
- money/numeric mentions;
- real-world entity candidates requiring research;
- continuity diff vs parent runtime;
- chapter delta candidate for promotion.

Эти отчёты должны помогать редактору, а не заменять литературный judgement.

## I. Regression test framework

Текущий `rules/regressions.yaml` развей так, чтобы regression lock мог иметь:

- stable rule ID;
- owner family;
- severity;
- description;
- positive examples;
- negative examples;
- detection type: deterministic / heuristic / semantic;
- fixture/test path;
- affected stages;
- introduced-by author correction/reference;
- superseded_by.

Там, где правило можно проверить машиной, должен быть test fixture.

## J. Freeze manifest

Freeze должен быть cryptographic/evidence based.

Минимум bind hashes для:

- exact chapter text;
- parent runtime;
- relevant character state;
- applicable regression/rules manifest;
- research/source manifest;
- QA manifest;
- generated artifact manifest.

Изменение любого dependency должно инвалидировать freeze.

## K. Promotion command

Сделай единый безопасный promotion workflow/CLI, например концептуально:

`python scripts/promote_chapter.py 025 --author-approved`

Но не используй такой флаг как способ подделать моё одобрение. Реальный author approval должен быть заранее записан отдельным явным evidence record.

Promotion должен:

1. проверить exact frozen hash;
2. проверить все blocking QA;
3. проверить author approval evidence;
4. применить declared chapter delta;
5. обновить runtime;
6. обновить character/system/arc state;
7. закрыть текущую production unit;
8. создать следующую `NOT_STARTED` unit;
9. сформировать promotion report;
10. завершиться атомарно либо не менять authority state.

## L. CI architecture

Раздели workflow на понятные jobs/checks, например:

- repository integrity;
- schema validation;
- canon/runtime invariants;
- research provenance/freshness;
- regression deterministic checks;
- text signal artifact generation;
- tests;
- Vale;
- optional heavier language QA;
- freeze verification;
- PDF provenance/preflight, когда появится безопасный source text.

Если тяжёлые проверки дороги/медленны, раздели fast required gates и optional/manual semantic-support jobs.

Pin GitHub Actions по SHA или иначе обеспечь supply-chain reproducibility.

## M. CI artifacts/reporting

GitHub Actions должен по возможности сохранять удобный `qa-report` artifact, который содержит:

- machine summary;
- PASS/BLOCK/REVIEW counts;
- dependency hashes;
- generated audits;
- stale evidence list;
- research warnings;
- freeze status.

Чтобы в новом чате можно было не перечитывать сотни логов, а скачать один reproducible report.

## N. Drive <-> GitHub sync

Не делай опасный blind bidirectional sync.

Сначала спроектируй **sync manifest + conflict detection**:

- GitHub source ID/path;
- Drive file ID;
- last known hashes/revisions;
- direction allowed;
- authority owner;
- last sync time;
- conflict state.

Любой conflict между Drive и GitHub должен быть видимым, а не автоматически затираться.

Если в текущем чате Drive connector недоступен — не притворяйся, что синхронизация выполнена. Сделай сторону GitHub/spec и явно укажи ограничение.

## O. PDF provenance

Пока repository public и полного frozen prose в нём нет, не притворяйся, что PDF pipeline полностью воспроизводим.

Но подготовь архитектуру так, чтобы позже PDF:

- строился из exact frozen source;
- сохранял source hash;
- проходил technical preflight;
- имел rendered visual QA evidence;
- становился deliverable только после обеих проверок.

## P. Security / dependency hygiene

Добавь разумные автоматические проверки зависимостей и workflows, если это не превращает repo в DevSecOps-пародию.

Рассмотри подходящие готовые GitHub-инструменты для dependency/security audit, pinning и static checks. Проверяй актуальность перед подключением.

# Как работать

Не ограничивайся советами. Если доступ к GitHub позволяет, **вноси изменения реально**.

Для существенного этапа:

1. inspect current main;
2. составь короткий implementation plan;
3. создай branch;
4. внеси код/config/tests/docs;
5. запусти/дождись CI;
6. если CI упал — открой logs, найди настоящую причину и исправь;
7. повторяй до green для required checks;
8. открой PR с понятным summary;
9. проверь финальный PR/CI;
10. merge только если scope действительно готов и нет blocking failure.

Не объявляй работу сделанной по факту создания файлов. Нужна execution evidence.

# Что не делать

- Не начинай писать Ch25 только потому, что `current/025` существует.
- Не создавай сюжетные факты для удобства инфраструктуры.
- Не превращай semantic литературные правила в слепой auto-rewrite.
- Не заменяй мой author approval модельным решением.
- Не повышай proposal/plan/belief до objective fact.
- Не тащи целый autonomous novel framework, если нам нужна одна его функция.
- Не выдумывай несуществующие библиотеки.
- Не говори «готово», пока проверки не были реально выполнены.

# Приоритет реализации

Если текущий repo действительно соответствует v1, двигайся примерно так:

**Phase 1 — audit/hardening**
- repo/CI audit;
- dependency health;
- schema gaps;
- improve tests;
- security/pinning.

**Phase 2 — state/provenance**
- fact IDs;
- knowledge model;
- research ledger;
- typed character/runtime state.

**Phase 3 — dependency invalidation**
- graph;
- stale evidence engine;
- robust freeze manifest.

**Phase 4 — chapter QA artifacts**
- dialogue/narration extracts;
- signal reports;
- continuity delta;
- research/entity candidates.

**Phase 5 — lifecycle/promotion**
- state machine;
- author approval evidence;
- atomic promotion command;
- next chapter creation.

**Phase 6 — integration/reporting**
- CI artifacts;
- Drive sync manifest;
- PDF provenance foundation.

Если в ходе аудита выяснится, что другой порядок технически лучше, измени порядок и объясни это в PR, но не выбрасывай сами цели.

# Финальный отчёт в чате

После реальной работы дай мне компактный, но содержательный отчёт:

1. что именно изменено;
2. какие готовые third-party инструменты были найдены и какие реально подключены;
3. какие рассмотрены, но отвергнуты и почему;
4. какие новые machine invariants теперь существуют;
5. какие CI jobs реально прошли;
6. какие failures были пойманы и исправлены;
7. ссылка/номер PR и merge status;
8. что остаётся главным bottleneck для следующей итерации.

Не засоряй отчёт внутренней цепочкой рассуждений.

---
