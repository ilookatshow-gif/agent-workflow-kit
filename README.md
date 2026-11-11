# Turn meeting notes into a reviewed task register

**Agent Workflow Kit** checks proposed personal commitments against exact note
spans, then exports the rows explicitly accepted in a supplied human-review
record. You get a local UTF-8 CSV with owners, titles, due dates and source
quotes, plus hashes identifying the input versions.

A matching quote establishes a text match. It does not establish a commitment,
an agreed deadline, completeness or a person's identity. The five-case example
makes this visible: a question passes the mechanical checks and is still
rejected by the supplied review decision.

Python 3.9+, standard library only. No model, API key, account or paid core.
This kit does not extract actions automatically, fetch a meeting recording,
authenticate the reviewer, send messages or create tasks in a live system.
It supplies one repeatable process and its local checks.

Prepared by **Дмитрий Лукашов / Dmitry Lukashov**, part of
[Lookatshow's open tools](https://github.com/ilookatshow-gif/lookatshow-open-tools).
[Русский](README.ru.md) · [MIT](LICENSE) · [Authorship and rights](NOTICE.md)

## Run the invented example

Unpack release v0.1.0 into a new folder and run:

```bash
python3 -B workflow_kit.py --json doctor
python3 -B workflow_kit.py --json review examples/source.json examples/candidates.json
python3 -B workflow_kit.py --json export examples/source.json examples/candidates.json examples/decisions.json --output ./demo-tasks.csv
```

The review has **five candidates: three mechanically consistent, two needing
review**. Its exit code is **1**, deliberately. The supplied decisions accept
two candidates and reject three, so the export exits **0** and writes two task
rows. Compare the actual bundled [review JSON](examples/review.json) and
[CSV](examples/tasks.csv) with your output.

| Candidate | Mechanical check | Supplied human decision |
|---|---|---|
| A01: prepare the plan by an explicit date | Consistent | Accept |
| A02: check two totals, without an agreed deadline | Consistent | Accept; due date stays empty |
| A03: fabricated quote against an existing line | Quote mismatch | Reject |
| A04: exact quote assigned to another speaker | Owner/speaker mismatch | Reject |
| A05: a question or proposal about Friday | Consistent | Reject: not a personal commitment |

The notes, candidate extraction and review are all invented teaching inputs.
They are not a captured model response, real meeting or Lookatshow sales result.
The sixth source line has no candidate; the CLI does not check extraction
completeness.

For a preview without writing a CSV:

```bash
python3 -B workflow_kit.py --json demo
```

`demo --output NEW_FILE.csv` writes the same accepted register. Existing files
are preserved unless `--replace` is supplied explicitly. Do not overwrite the
bundled example or the source inputs.

## Install a command

On POSIX, choose a new dedicated prefix and a command directory:

```bash
python3 -B install.py --prefix "$HOME/.local/share/agent-workflow-kit" --bin-dir "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
cd /tmp
agent-workflow-kit --json doctor
agent-workflow-kit --json demo --output ./meeting-tasks-demo.csv
```

The launcher uses the exact Python interpreter used for installation. Keep that
interpreter available. Occupied prefixes and commands are preserved; choose
other paths if they conflict. Symlinked path components are refused; use real
directories. Keep your own inputs and outputs outside the installation prefix.

The native installer is POSIX-only. On Windows, use the source command, such as
`python workflow_kit.py ...`, choosing the Python command available on your
machine. A CI configuration is separate from evidence that it ran successfully.

Optional `agent-workflow-kit --json onboard` shows the author's links once and
creates a local `.onboarded` marker. Ordinary JSON and CSV contain no promotional
inserts or telemetry.

Uninstall from any folder with the same paths:

```bash
python3 -B "$HOME/.local/share/agent-workflow-kit/uninstall.py" --prefix "$HOME/.local/share/agent-workflow-kit" --bin-dir "$HOME/.local/bin"
```

Uninstall checks the exact owned-file hashes and preserves other user files.
If the installation is modified or incomplete, inspect that state before
trying again.

## Use it on authorised notes

Follow [the process](docs/WORKFLOW.md) and [the input contract](docs/INPUT-CONTRACT.md):

1. Preserve a source version with stable meeting, line and participant IDs.
2. Ask an agent or operator for candidate personal commitments in this exact
   JSON format. Do not infer missing owners or due dates.
3. Run `review SOURCE CANDIDATES`; compare every candidate with the actual
   notes, including questions, proposals and omissions the checker cannot judge.
4. Record a real human decision for every candidate. Bind that record to the
   exact source and candidate file hashes. A reviewer ID in JSON is a declaration,
   not authentication or proof of review.
5. Run `export SOURCE CANDIDATES DECISIONS --output NEW_FILE.csv`. Stale review
   hashes, missing decisions or a mechanically invalid accepted action block
   the entire export. Explicitly rejected bad candidates remain counted and
   are omitted from the accepted register.

The package uses `.gitattributes` to preserve LF in Git checkouts, including
Windows, because the teaching file hashes bind raw bytes. Your own JSON may
use other valid whitespace, but changing its line endings changes the version
that must be reviewed. No global Git setting is required.

Changing a source byte, a candidate or its declared due date requires a review
of the new version. Do not update old decision hashes merely to obtain a clean
export. Source spans use Python Unicode code-point offsets, zero-based and
end-exclusive; browser UTF-16 offsets are different.

The CSV is a local register, not a vendor-specific import contract. Text cells
whose trimmed start is `=`, `+`, `-` or `@` receive a leading apostrophe for
spreadsheet viewing; `formula_escaped_cells` reports the count. The original
JSON remains unchanged. This bounded mitigation changes those displayed cells
and does not certify every spreadsheet consumer.

All CLI processing is local. An agent or service that reads your notes has its
own data-access boundary; the offline CLI does not make a cloud agent local.
Do not commit private notes, review records or outputs into this public package.

## JSON and exit codes

Normal output is JSON, with `--json` available explicitly. It uses ASCII escapes
without losing Unicode and LF byte endings on ordinary stdout across hosts.
Saved CSV is UTF-8 with LF. Errors have `ok:false` and a code, without dumping
supplied payloads.

| Command | Exit 0 | Exit 1 | Exit 2 |
|---|---|---|---|
| `review` | All supplied citations mechanically consistent | Complete report with findings | Invalid input or execution error |
| `export` | Complete eligible CSV written | Batch blocked; no CSV written | Invalid input, occupied path or IO error |
| `demo` | Eligible invented register previewed or written | Invented batch blocked | Execution error |

An all-rejected batch may produce a header-only CSV with `accepted:0` and the
explicit rejected count. That is a recorded rejection outcome, not invented
work or proof that no real commitments exist. Inspect the JSON and exit code
together; do not suppress every nonzero code with `|| true`.

## Give an agent a bounded task

> Use Agent Workflow Kit on these authorised local note and candidate files.
> Run doctor and review; preserve the exit code and show every finding. Explain
> what exact source spans establish and what remains a semantic human decision.
> Do not invent owners, due dates, missing quotes or reviewer acceptance. After
> I supply the review record, check its exact file hashes and export to a new
> CSV only if the complete batch is eligible. Return the file path, its hash,
> accepted/rejected counts and unresolved checks. Do not contact anyone or
> create live tasks as part of this local export.

The [repo-local skill](skills/agent-workflow-kit/SKILL.md) explains this order
for agents that can run local Python commands. It is not an MCP server or a
compatibility certification for every host. [Company Knowledge Kit](https://github.com/ilookatshow-gif/company-knowledge-kit)
finds literal document evidence; this kit reviews a proposed task register.

## Learning and implementation

Prepared by **Дмитрий Лукашов**. [Practical AI notes](https://t.me/lookatsoul).
[Learn the process on your task](https://lookatshow.ru/executive?utm_source=github&utm_medium=open_module&utm_campaign=agent-workflow-kit&utm_content=readme_en_learn),
or [discuss one workflow implementation](https://lookatshow.ru/ai-implementation/?utm_source=github&utm_medium=open_module&utm_campaign=agent-workflow-kit&utm_content=readme_en_implementation).
Training and implementation are separate services. The MIT module requires no
subscription, registration, contact details or purchase.
