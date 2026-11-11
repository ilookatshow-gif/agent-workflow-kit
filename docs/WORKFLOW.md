# Meeting notes to a reviewed register

[Русский ниже](#из-заметок-встречи-в-проверенный-реестр).
This original process template covers proposed personal commitments from one
supplied note version. Adapt the roles and actual review method to the team's
authorised work. The CLI validates representations; it does not run the
meeting, extract meaning or operate a live task system.

| Stage | Responsible role | Input and check | Saved outcome |
|---|---|---|---|
| Preserve the source | Note owner | Authorised text, stable meeting/participant/line IDs, exact source version | Source JSON and provenance kept outside the public package |
| Propose candidates | Assigned agent or operator | Exact personal-commitment candidates, owner IDs, explicit or unknown due dates, source spans | Candidate JSON bound to source SHA-256 |
| Check citations | Local operator | Review every quote slice, source hash and speaker/owner relationship | Complete review JSON, including all findings |
| Judge meaning | Assigned human reviewer | Read source context, distinguish commitments from questions/proposals, check owner/date claims and omissions | Accept/reject decision per candidate with exact source/candidate hashes |
| Export the register | Local operator | Full decision coverage, unchanged inputs, accepted rows mechanically valid | Deterministic local task CSV and readback metadata |
| Handle a later delivery, if assigned | Authorised task-system operator | Check exact account, destination and duplicate state; save intent before one write | Actual provider object IDs and readback, separate from local export |
| Close the work | Process owner | Compare local file, actual delivered objects if relevant, and unresolved human decisions | A stated completion scope; local export is not live delivery or task completion |

## Apply the checks to the example

A01 and A02 have exact citations and the supplied reviewer accepts them. A02's
notes do not establish an agreed deadline, so its due date remains null/empty.
A03's fabricated quote and A04's owner mismatch are rejected. A05 quotes a real
question accurately: it is mechanically consistent, yet the reviewer rejects
it because no personal commitment was made.

That last case is deliberate. The checker cannot determine promise, intention,
authority or completeness from a span match. The sixth source line is not a
candidate and is not automatically accounted for as a task. Keep a human check
for omissions; do not call the proposed list exhaustive.

## Exceptions and restart

- SOURCE_HASH_MISMATCH: locate the source version used for the candidates or
  produce a newly reviewed candidate file for the changed source. Do not merely
  replace a digest to make an old extraction appear current.
- A missing line, invalid span or changed quote: open the relevant source.
  Correct the candidate only when the evidence supports it, preserving history.
- OWNER_SPEAKER_MISMATCH: this kit's bounded workflow covers personal
  commitments by the cited speaker. Delegation and assignments by third parties
  need another explicit interpretation; do not manufacture a matching owner.
- A technically consistent question: reject or clarify it through the real
  review process. The CLI has no semantic approval command.
- Missing decisions or stale review hashes: complete a real review of the
  actual version. Preserve the earlier record, including rejection reasons.
- A mechanically invalid accepted row: export stops for the whole batch.
  Rejected bad rows may remain in the review record with their reasons.
- An occupied output path: use a new one or select --replace deliberately.
  An input path or hard-link collision is never an intended output destination.

Keep source, candidates, decisions and the actual exported CSV together as a
versioned local evidence set. Input hashes identify bytes, not authenticated
review. A new source/candidate version is a new review unit. The export writes
no provider state and has no remote retry command.

If a later assigned delivery times out, first reconcile the exact target and
provider history. An uncertain response is not proof that a write failed.
Do not re-send a register or create duplicate tasks blindly. Local readiness,
provider delivery, customer agreement, task completion and payment are separate
outcomes.

## A useful completion criterion

The local stage closes when every candidate has a supplied decision, every
accepted row has valid technical evidence, the exported file is read back and
its hash/counts match. The semantic reviewer remains responsible for the
meaning and omissions. If all rows were rejected, record that result honestly;
do not add invented tasks to produce a nonempty register.

## Из заметок встречи в проверенный реестр

Это оригинальный шаблон процесса для предполагаемых личных обязательств из
одной версии заметок. Роли и способ реального разбора выбирает команда.
CLI проверяет предоставленные файлы: он не проводит встречу, не извлекает смысл
и не управляет живой системой задач.

| Этап | Кто отвечает | Что проверить | Что сохранить |
|---|---|---|---|
| Сохранить источник | Владелец заметок | Разрешённый текст, постоянные ID встречи, участников и строк, точную версию | JSON источника и его происхождение вне публичного пакета |
| Предложить кандидатов | Назначенный агент или оператор | Личные обязательства, ответственных, явные или неизвестные сроки, точные фрагменты | JSON кандидатов с SHA-256 источника |
| Проверить цитаты | Локальный оператор | Каждый фрагмент, хеш источника, соответствие говорящего и ответственного | Полный JSON проверки со всеми причинами |
| Разобрать смысл | Назначенный человек | Обещания, вопросы и предложения, ответственных, сроки и пропущенные задачи | Принятие или отклонение каждого кандидата по точным хешам файлов |
| Сохранить реестр | Локальный оператор | Полноту решений, неизменность входа и техническую корректность принятых строк | Детерминированный CSV и метаданные чтения результата |
| Передать дальше, если поручено | Уполномоченный оператор системы задач | Аккаунт, адрес назначения и дубли; намерение до одной записи | Реальные ID объектов и readback отдельно от локального экспорта |
| Закрыть работу | Владелец процесса | Локальный файл, фактическую передачу при её наличии и оставшиеся решения | Явную границу завершения; CSV не означает доставку или выполнение задач |

### Учебные строки

A01 и A02 имеют точные цитаты, предоставленный проверяющий принимает их. Для
A02 в заметках не установлен согласованный срок, поэтому поле остаётся пустым.
Выдуманную цитату A03 и несоответствие ответственного A04 отклоняют. A05 точно
цитирует вопрос: техническая проверка проходит, но личного обязательства нет,
и человек отклоняет кандидата.

Это отдельный обязательный разбор смысла. Совпадение фрагмента не определяет
обещание, намерение, полномочия или полноту. Шестая строка источника не включена
в кандидаты и не превращается в задачу автоматически. Пропуски проверяются
отдельно; исчерпывающий список программой не установлен.

### Исключения и повтор процесса

- SOURCE_HASH_MISMATCH: найдите исходную версию или подготовьте кандидатов для
  изменённого источника и проведите новую проверку. Не подменяйте один хеш,
  чтобы старое извлечение выглядело текущим.
- Отсутствующая строка, неправильные границы или другая цитата: откройте источник.
  Исправляйте кандидата по основанию, сохраняя прежний вариант.
- OWNER_SPEAKER_MISMATCH: здесь проверяются личные обязательства говорящего.
  Поручения от третьих лиц требуют отдельного разбора; совпадение не создаётся
  заменой ответственного ради результата проверки.
- Точный вопрос: отклоните его или уточните в реальном процессе. Семантического
  одобрения у CLI нет.
- Не хватает решения или устарели хеши: закончите проверку реальной версии.
  Сохраните прежний файл и причины отклонения.
- Человек принял технически неверную строку: блокируется весь экспорт. Явно
  отклонённые плохие строки могут остаться в решениях со своими причинами.
- Путь занят: выберите новый или явно укажите --replace. Входной файл и его
  hard link не становятся допустимой целью экспорта.

Храните источник, кандидатов, решения и полученный CSV как один набор версий.
Хеши указывают байты, а не удостоверяют проверку человеком. Новая версия входа
требует новой проверки. Экспорт не пишет провайдеру и не имеет удалённого retry.

Если позднее порученная передача завершилась тайм-аутом, сначала выясните исход
по точному объекту и истории провайдера. Неизвестный ответ не доказывает, что
запись не состоялась. Не создавайте дубли задач вслепую. Локальная готовность,
доставка, согласие клиента, выполнение задачи и оплата подтверждаются отдельно.

### Когда локальный этап завершён

По каждому кандидату есть решение, принятые строки технически допустимы,
CSV прочитан обратно, хеш и счётчики совпали. Смысл и пропуски остаются
ответственностью реального проверяющего. Полное отклонение допустимо как исход
разбора; добавлять выдуманные задачи ради непустого реестра нельзя.
