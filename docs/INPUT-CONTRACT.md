# Exact local input contract / Контракт локального входа

Run `agent-workflow-kit --json schema` for the machine-readable shapes. The
three complete invented inputs are [source](../examples/source.json),
[candidates](../examples/candidates.json) and [decisions](../examples/decisions.json).
This is the module's own JSON format, not an arbitrary transcript/CRM importer.

Команда `schema` показывает машинные схемы. Три учебных входа связаны выше.
Произвольные заметки или выгрузку нужно привести к этому формату, сохранив
происхождение, отсутствие данных и точную версию.

## Source / Источник

| Field | Meaning / Смысл |
|---|---|
| schema_version | Integer1 / Целое1 |
| meeting_id | Stable identifier / Постоянный ID встречи |
| participants | Unique records id,label; up to100 / Уникальные участники, до100 |
| lines | One to2000 records id,speaker_id,text / От1 до2000 строк |

Participant and line IDs are unique; each speaker_id refers to a supplied
participant. A line is one bounded nonblank text record, not a fetched recording.
Идентификаторы участников и строк уникальны, говорящий есть в списке участников.
Строка — предоставленный текст, а не загруженная запись встречи.

## Candidates / Кандидаты

| Field | Meaning / Смысл |
|---|---|
| schema_version,meeting_id | Version1 and matching meeting ID / Версия1 и тот же ID встречи |
| source_sha256 | SHA-256 of exact source file bytes / Хеш точных байтов источника |
| actions | One to500 records / От1 до500 кандидатов |
| Action fields | id,owner_id,title,due_date,source_line_id,start,end,quote |

Action IDs are unique. owner_id and source_line_id may be well-shaped but absent
from the source; that becomes a review finding. due_date is null or a real exact
YYYY-MM-DD calendar date. The CLI does not infer or verify that date from prose.
A matching owner/speaker ID is a local consistency condition for this personal-
commitment workflow, not identity authentication.

ID кандидатов уникальны. Не найденные в предоставленном источнике ответственный
или строка дают причину для проверки. due_date — null либо реальная календарная
дата YYYY-MM-DD. Программа не выводит и не подтверждает её по смыслу текста.
Совпадение ID говорящего и ответственного не удостоверяет личность.

start/end are signed integer Python Unicode code-point indices: zero-based,
end-exclusive. They are not UTF-16 indices or grapheme positions. Negative,
unordered or out-of-range spans are findings rather than silently corrected
slices. The quote must match that exact source substring. Browser offsets must
be converted deliberately before use.

start/end — целые индексы Unicode code points строки Python: от нуля, правая
граница не входит. Индексы UTF-16 браузера и позиции графем отличаются.
Отрицательные, перепутанные или выходящие за строку границы дают причину для
проверки; программа не исправляет их молча. Цитата должна совпасть посимвольно.

## Decisions / Решения

| Field | Meaning / Смысл |
|---|---|
| schema_version,meeting_id | Version1 and matching meeting / Версия1 и та же встреча |
| source_sha256,candidates_sha256 | Exact file versions reviewed / Точные проверенные версии файлов |
| reviewer_id,reviewed_on | Supplied reviewer ID and real YYYY-MM-DD date / Заявленные ID проверяющего и дата |
| decisions | Up to500 records action_id,decision,reason / До500 решений |

Each action can have at most one decision. Unknown action IDs and duplicate
decisions are invalid. decision is accept or reject; rejection requires a
nonblank reason, acceptance may have an empty reason. Missing decisions are
well-shaped but block the entire export. All candidates need a decision.

Не больше одного решения на кандидата. Неизвестные ID и дубли запрещены.
Решение — accept или reject. Для отказа нужна непустая причина; для принятия
причина может быть пустой. Пропущенное решение блокирует весь экспорт.

reviewer_id and reviewed_on are declarations, not an authenticated signature,
proof of actual reading or an implicit current-time check. They do not create
human approval. Preserve the real review evidence separately. Any byte change
to a source or candidate file changes its SHA-256 and requires review of the
new version, even when the JSON meaning looks similar.

ID и дата не являются подписью, доказательством прочтения или проверкой текущего
времени. Они не создают согласие человека. Исходное свидетельство разбора
хранится отдельно. Любая правка байта источника или кандидатов требует
проверки новой версии, даже если смысл JSON кажется прежним.

To obtain the source digest before preparing a candidate file:

```bash
python3 -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('source.json').read_bytes()).hexdigest())"
```

Use the review result's source_sha256 and candidates_sha256 for the exact input
versions, after the actual human review. Do not copy a newly computed digest
into an old decision merely to bypass refusal.

## Mechanical findings / Причины технической проверки

| Code | Meaning / Смысл |
|---|---|
| SOURCE_HASH_MISMATCH | Candidates refer to another source version / Другая версия источника |
| LINE_NOT_FOUND | Supplied line absent / В предоставленном источнике нет строки |
| OWNER_NOT_FOUND | Supplied owner absent / В предоставленных участниках нет ответственного |
| OWNER_SPEAKER_MISMATCH | Owner is not the cited speaker / Ответственный отличается от говорящего |
| SPAN_OUT_OF_RANGE | Invalid ordered bounds for the actual line / Границы не подходят к реальной строке |
| QUOTE_MISMATCH | Exact slice differs / Посимвольное несовпадение |

Several reasons may apply to one row. No reason means mechanically consistent,
not semantically accepted. A05 in the example quotes a question exactly and is
therefore consistent, but its supplied human decision is reject.

У строки может быть несколько причин. Их отсутствие означает техническую
согласованность. A05 точно цитирует вопрос и проходит проверку, но в файле
решений человек отклоняет его.

## Export blockers / Причины отказа экспорта

| Code | Meaning / Смысл |
|---|---|
| REVIEW_SOURCE_HASH_MISMATCH | Decision record belongs to another source / Решения по другому источнику |
| REVIEW_CANDIDATES_HASH_MISMATCH | Decision record belongs to another candidate version / Решения по другим кандидатам |
| DECISION_MISSING | No decision for a candidate / Не хватает решения |
| ACCEPTED_ACTION_INVALID | An accepted action has a mechanical finding / Принята технически неверная строка |

The whole export is blocked if any applies; no partial CSV is created.
Mechanically bad but explicitly rejected candidates may be omitted with their
rejected count. All-rejected input may yield only headers with accepted0.

Любая причина блокирует весь экспорт без частичного CSV. Явно отклонённые
плохие кандидаты могут остаться в решениях и счётчике отклонений. Если все
отклонены, допустим один заголовок с accepted0, без выдуманных задач.

## Bounds and local output / Пределы и выход

Each file is UTF-8 JSON, at most1MiB before parsing. Exact keys are required;
extra/duplicate JSON keys, NaN/Infinity, booleans in integer fields, controls,
surrogates and oversized collections/strings are refused. IDs follow
[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}; label<=160,text<=4000,title<=500,quote<=2000,
reason<=2000. Consult schema for the exact current field and span bounds.
Invalid JSON/date/shape, mismatched meeting IDs or unknown decision IDs give
exit2 without a new output. The error JSON does not dump the supplied payload.

Файл ограничен1МиБ UTF-8 до разбора. Ключи заданы точно; лишние и повторяющиеся
ключи, NaN/Infinity, логические значения вместо чисел, управляющие символы,
суррогаты и превышение пределов отклоняются. Точные границы показывает schema.
Ошибки формата, даты, ID встречи или решений дают код2 без нового результата.

CSV columns in order: action_id,owner_id,owner_label,title,due_date,meeting_id,
source_line_id,quote. Accepted action order is preserved. Output is UTF-8 with
LF; null dates become empty cells. csv.writer quotes separators/quotes.
A leading apostrophe is added to text cells whose lstrip() starts with =,+,-,@;
formula_escaped_cells counts the altered cells. Original JSON is preserved.
This bounded spreadsheet-viewing measure is not universal protection or a
ready import format for any particular service.

Порядок столбцов и принятых кандидатов сохраняется. CSV — UTF-8/LF, null-срок
пустой. Внешние системы модуль не меняет. У формулоподобных текстовых ячеек
появляется апостроф, число изменений указано в JSON; исходные файлы сохранены.

Review reports use evidence_basis=supplied_note_spans_only, input hashes,
summary{actions,consistent,needs_review} and all rows with findings. Export
reports include ready, accepted/rejected counts, formula_escaped_cells, exact
output hash/size, exported_actions (zero when blocked) and declared reviewer
metadata. Review rows include the proposed title/date/quote and cited source
text/speaker for human comparison. Demo wraps review and export
and labels itself synthetic. Read exit status together with JSON.
