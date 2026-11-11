#!/usr/bin/env python3
"""Offline meeting-note citation review and explicitly reviewed task CSV export."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata

VERSION = "0.1.0"
MAX_BYTES = 1024 * 1024
MAX_JSON_NESTING = 32
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$"
HASH_PATTERN = r"^[0-9a-f]{64}$"
BASIS = "supplied_note_spans_only"
FINDINGS = ("SOURCE_HASH_MISMATCH", "LINE_NOT_FOUND", "OWNER_NOT_FOUND",
            "OWNER_SPEAKER_MISMATCH", "SPAN_OUT_OF_RANGE", "QUOTE_MISMATCH")
EXPORT_FINDINGS = ("REVIEW_SOURCE_HASH_MISMATCH", "REVIEW_CANDIDATES_HASH_MISMATCH",
                   "DECISION_MISSING", "ACCEPTED_ACTION_INVALID")
CSV_COLUMNS = ("action_id", "owner_id", "owner_label", "title", "due_date",
               "meeting_id", "source_line_id", "quote")


class InputError(Exception):
    """Payload-free public error code."""


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def string(maximum, minimum=1, **extra):
    return dict({"type": "string", "minLength": minimum, "maxLength": maximum}, **extra)


_ID = string(80, pattern=ID_PATTERN)
_HASH = string(64, pattern=HASH_PATTERN)
_DATE = string(10, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", format="date")
SOURCE_SCHEMA = obj({
    "schema_version": {"type": "integer", "const": 1}, "meeting_id": _ID,
    "participants": {"type": "array", "minItems": 1, "maxItems": 100,
                     "items": obj({"id": _ID, "label": string(160)})},
    "lines": {"type": "array", "minItems": 1, "maxItems": 2000,
              "items": obj({"id": _ID, "speaker_id": _ID, "text": string(4000)})},
})
CANDIDATES_SCHEMA = obj({
    "schema_version": {"type": "integer", "const": 1}, "meeting_id": _ID,
    "source_sha256": _HASH,
    "actions": {"type": "array", "minItems": 1, "maxItems": 500,
                "items": obj({"id": _ID, "owner_id": _ID, "title": string(500),
                    "due_date": {"anyOf": [_DATE, {"type": "null"}]},
                    "source_line_id": _ID,
                    "start": {"type": "integer", "minimum": -999999999999, "maximum": 999999999999},
                    "end": {"type": "integer", "minimum": -999999999999, "maximum": 999999999999},
                    "quote": string(2000)})},
})
DECISIONS_SCHEMA = obj({
    "schema_version": {"type": "integer", "const": 1}, "meeting_id": _ID,
    "source_sha256": _HASH, "candidates_sha256": _HASH,
    "reviewer_id": _ID, "reviewed_on": _DATE,
    "decisions": {"type": "array", "maxItems": 500,
                  "items": obj({"action_id": _ID,
                    "decision": {"type": "string", "enum": ["accept", "reject"]},
                    "reason": string(2000, minimum=0)})},
})
INPUT_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema",
    "source": SOURCE_SCHEMA, "candidates": CANDIDATES_SCHEMA, "decisions": DECISIONS_SCHEMA,
    "semantic_checks": "Unique IDs; known source speakers; matching meeting IDs; real dates; control/surrogate-free strings; nonblank reject reasons. Span findings and exact raw-byte hashes are checked by the CLI. This collection describes three file schemas, not one combined input."}


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise InputError("OBJECT_FIELDS_INVALID")


def text(value, maximum, empty=False):
    if (not isinstance(value, str) or len(value) > maximum or
            (not empty and not value.strip()) or
            any(unicodedata.category(c) in ("Cc", "Cs") for c in value)):
        raise InputError("STRING_INVALID")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(ID_PATTERN, value):
        raise InputError("IDENTIFIER_INVALID")


def digest_value(value):
    if not isinstance(value, str) or not re.fullmatch(HASH_PATTERN, value):
        raise InputError("HASH_INVALID")


def date_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise InputError("DATE_INVALID")
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise InputError("DATE_INVALID")


def collection(value, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise InputError("COLLECTION_INVALID")


def unique(rows, key):
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise InputError("DUPLICATE_ID")


def header(value, fields):
    exact(value, fields)
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise InputError("SCHEMA_VERSION_INVALID")
    identifier(value["meeting_id"])


def validate_source(source):
    header(source, ("schema_version", "meeting_id", "participants", "lines"))
    collection(source["participants"], 100, 1)
    for row in source["participants"]:
        exact(row, ("id", "label")); identifier(row["id"]); text(row["label"], 160)
    unique(source["participants"], "id")
    people = {row["id"] for row in source["participants"]}
    collection(source["lines"], 2000, 1)
    for row in source["lines"]:
        exact(row, ("id", "speaker_id", "text"))
        identifier(row["id"]); identifier(row["speaker_id"]); text(row["text"], 4000)
        if row["speaker_id"] not in people:
            raise InputError("SOURCE_SPEAKER_UNKNOWN")
    unique(source["lines"], "id")
    return source


def validate_candidates(candidates):
    header(candidates, ("schema_version", "meeting_id", "source_sha256", "actions"))
    digest_value(candidates["source_sha256"])
    collection(candidates["actions"], 500, 1)
    for row in candidates["actions"]:
        exact(row, ("id", "owner_id", "title", "due_date", "source_line_id", "start", "end", "quote"))
        for key in ("id", "owner_id", "source_line_id"):
            identifier(row[key])
        text(row["title"], 500); text(row["quote"], 2000)
        if row["due_date"] is not None:
            date_value(row["due_date"])
        if any(type(row[key]) is not int or abs(row[key]) > 999999999999 for key in ("start", "end")):
            raise InputError("SPAN_INTEGER_INVALID")
    unique(candidates["actions"], "id")
    return candidates


def validate_decisions(decisions, candidates):
    header(decisions, ("schema_version", "meeting_id", "source_sha256", "candidates_sha256",
                       "reviewer_id", "reviewed_on", "decisions"))
    digest_value(decisions["source_sha256"]); digest_value(decisions["candidates_sha256"])
    identifier(decisions["reviewer_id"]); date_value(decisions["reviewed_on"])
    collection(decisions["decisions"], 500)
    ids = {row["id"] for row in candidates["actions"]}
    for row in decisions["decisions"]:
        exact(row, ("action_id", "decision", "reason")); identifier(row["action_id"])
        if row["action_id"] not in ids:
            raise InputError("DECISION_ACTION_UNKNOWN")
        if row["decision"] not in ("accept", "reject"):
            raise InputError("DECISION_INVALID")
        text(row["reason"], 2000, empty=row["decision"] == "accept")
    unique(decisions["decisions"], "action_id")
    if decisions["meeting_id"] != candidates["meeting_id"]:
        raise InputError("MEETING_ID_MISMATCH")
    return decisions


def pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise InputError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def integer(value):
    if len(value.lstrip("-")) > 12:
        raise InputError("INTEGER_TOO_LARGE")
    return int(value)


def constant(value):
    raise InputError("NONFINITE_JSON")


def floating(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise InputError("NONFINITE_JSON")
    return parsed


def check_json_nesting(value):
    """Bound container depth before decoding, independent of Python recursion limits.

    Brackets inside quoted strings are data. JSON syntax, including malformed
    escapes and mismatched delimiters, remains the standard decoder's job.
    """
    depth = 0
    quoted = False
    escaped = False
    for character in value:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING:
                raise InputError("JSON_TOO_DEEP")
        elif character in "]}":
            depth -= 1


def parse_json(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise InputError("INPUT_TOO_LARGE")
    try:
        value = raw.decode("utf-8")
        check_json_nesting(value)
        return json.loads(value, object_pairs_hook=pairs,
                          parse_constant=constant, parse_int=integer, parse_float=floating)
    except (ValueError, UnicodeError, RecursionError):
        raise InputError("JSON_INVALID")


def load_json(path):
    try:
        if not Path(path).is_file():
            raise InputError("INPUT_READ_ERROR")
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
    except (OSError, ValueError):
        raise InputError("INPUT_READ_ERROR")
    return parse_json(raw), sha256(raw)


def review(source, candidates, source_sha, candidates_sha):
    validate_source(source); validate_candidates(candidates)
    if source["meeting_id"] != candidates["meeting_id"]:
        raise InputError("MEETING_ID_MISMATCH")
    lines = {row["id"]: row for row in source["lines"]}
    people = {row["id"]: row for row in source["participants"]}
    rows = []
    for action in candidates["actions"]:
        codes = set()
        if candidates["source_sha256"] != source_sha:
            codes.add("SOURCE_HASH_MISMATCH")
        line = lines.get(action["source_line_id"])
        if action["owner_id"] not in people:
            codes.add("OWNER_NOT_FOUND")
        if line is None:
            codes.add("LINE_NOT_FOUND")
        else:
            if action["owner_id"] != line["speaker_id"]:
                codes.add("OWNER_SPEAKER_MISMATCH")
            start, end = action["start"], action["end"]
            if not 0 <= start < end <= len(line["text"]):
                codes.add("SPAN_OUT_OF_RANGE")
            elif line["text"][start:end] != action["quote"]:
                codes.add("QUOTE_MISMATCH")
        rows.append({"action_id": action["id"], "owner_id": action["owner_id"],
            "owner_label": people[action["owner_id"]]["label"] if action["owner_id"] in people else None,
            "title": action["title"], "due_date": action["due_date"],
            "source_line_id": action["source_line_id"], "start": action["start"], "end": action["end"],
            "quote": action["quote"], "source_speaker_id": line["speaker_id"] if line else None,
            "source_text": line["text"] if line else None,
            "classification": "needs_review" if codes else "consistent",
            "findings": [code for code in FINDINGS if code in codes]})
    consistent = sum(row["classification"] == "consistent" for row in rows)
    return {"ok": True, "command": "review", "version": VERSION, "evidence_basis": BASIS,
        "source_sha256": source_sha, "candidates_sha256": candidates_sha,
        "meeting_id": source["meeting_id"],
        "summary": {"actions": len(rows), "consistent": consistent, "needs_review": len(rows)-consistent},
        "rows": rows}


def safe_cell(value):
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value, True
    return value, False


def export_plan(source, candidates, decisions, source_sha, candidates_sha, decisions_sha):
    checked = review(source, candidates, source_sha, candidates_sha)
    validate_decisions(decisions, candidates)
    supplied = {row["action_id"]: row for row in decisions["decisions"]}
    checked_rows = {row["action_id"]: row for row in checked["rows"]}
    findings = []
    if decisions["source_sha256"] != source_sha:
        findings.append({"code": "REVIEW_SOURCE_HASH_MISMATCH"})
    if decisions["candidates_sha256"] != candidates_sha:
        findings.append({"code": "REVIEW_CANDIDATES_HASH_MISMATCH"})
    for row in candidates["actions"]:
        item = supplied.get(row["id"])
        if item is None:
            findings.append({"code": "DECISION_MISSING", "action_id": row["id"]})
        elif item["decision"] == "accept" and checked_rows[row["id"]]["findings"]:
            findings.append({"code": "ACCEPTED_ACTION_INVALID", "action_id": row["id"],
                             "reasons": checked_rows[row["id"]]["findings"]})
    accepted = [row for row in candidates["actions"] if supplied.get(row["id"], {}).get("decision") == "accept"]
    rejected = sum(item["decision"] == "reject" for item in supplied.values())
    result = {"ok": True, "command": "export", "version": VERSION,
        "evidence_basis": BASIS, "meeting_id": source["meeting_id"],
        "ready": not findings, "accepted": len(accepted), "rejected": rejected,
        "exported_actions": 0, "formula_escaped_cells": 0,
        "output_sha256": None, "output_bytes": 0,
        "reviewer_declared": True, "reviewer_id": decisions["reviewer_id"],
        "reviewed_on": decisions["reviewed_on"], "source_sha256": source_sha,
        "candidates_sha256": candidates_sha, "decisions_sha256": decisions_sha,
        "findings": findings}
    if findings:
        return result, None
    people = {row["id"]: row["label"] for row in source["participants"]}
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    escaped = 0
    for row in accepted:
        values = (row["id"], row["owner_id"], people[row["owner_id"]], row["title"],
                  row["due_date"] or "", source["meeting_id"], row["source_line_id"], row["quote"])
        safe = []
        for value in values:
            transformed, changed = safe_cell(value); safe.append(transformed); escaped += int(changed)
        writer.writerow(safe)
    raw = output.getvalue().encode("utf-8")
    result.update(exported_actions=len(accepted), formula_escaped_cells=escaped,
                  output_sha256=sha256(raw), output_bytes=len(raw))
    return result, raw


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2)+"\n").encode("ascii")


def emit(value):
    raw = json_bytes(value)
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(raw); stream.flush()
    else:
        sys.stdout.write(raw.decode("ascii")); sys.stdout.flush()


def write_output(path, raw, input_paths, replace=False):
    target = Path(os.path.abspath(str(path)))
    for part in (target,) + tuple(target.parents):
        if part.is_symlink():
            raise InputError("OUTPUT_SYMLINK_REFUSED")
    for item in input_paths:
        original = Path(item)
        try:
            collision = target.resolve() == original.resolve() or (target.exists() and os.path.samefile(str(target), str(original)))
        except OSError:
            raise InputError("OUTPUT_IO_ERROR")
        if collision:
            raise InputError("OUTPUT_IS_INPUT")
    if target.exists() and not replace:
        raise InputError("OUTPUT_EXISTS")
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".workflow-tasks-", dir=str(target.parent))
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        if replace:
            os.replace(temporary, str(target))
        else:
            os.link(temporary, str(target))
    except OSError:
        raise InputError("OUTPUT_IO_ERROR")
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def onboard():
    marker = Path(__file__).resolve().parent / ".onboarded"
    if marker.is_symlink():
        raise InputError("ONBOARD_MARKER_INVALID")
    if marker.exists():
        if not marker.is_file() or marker.stat().st_size != len(VERSION)+1 or marker.read_bytes() != (VERSION+"\n").encode("ascii"):
            raise InputError("ONBOARD_MARKER_INVALID")
        return {"ok": True, "command": "onboard", "version": VERSION, "already_shown": True}
    descriptor = os.open(str(marker), os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0), 0o600)
    with os.fdopen(descriptor,"wb") as handle:
        handle.write((VERSION+"\n").encode("ascii"))
    return {"ok": True, "command": "onboard", "version": VERSION, "already_shown": False,
        "author": "Дмитрий Лукашов / Dmitry Lukashov",
        "message": "Review the invented notes and human decisions first. Exact quotation is not proof of a personal commitment.",
        "practical_notes": "https://t.me/lookatsoul",
        "learn": "https://lookatshow.ru/executive?utm_source=github&utm_medium=open_module&utm_campaign=agent-workflow-kit&utm_content=onboard_learn",
        "implementation": "https://lookatshow.ru/ai-implementation/?utm_source=github&utm_medium=open_module&utm_campaign=agent-workflow-kit&utm_content=onboard_implementation"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError("CLI_USAGE")


def main(argv=None):
    try:
        parser=Parser(description="Review meeting-note spans and export explicitly accepted personal commitments offline.")
        parser.add_argument("--json", action="store_true", help="Stable ASCII JSON, also the default.")
        commands=parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        for name in ("doctor","schema","onboard"):
            commands.add_parser(name)
        reviewer=commands.add_parser("review");reviewer.add_argument("source");reviewer.add_argument("candidates")
        exporter=commands.add_parser("export")
        for name in ("source","candidates","decisions"):
            exporter.add_argument(name)
        exporter.add_argument("--output", required=True);exporter.add_argument("--replace", action="store_true")
        demo=commands.add_parser("demo");demo.add_argument("--output");demo.add_argument("--replace", action="store_true")
        args=parser.parse_args(argv)
        if sys.version_info < (3,9):
            raise InputError("PYTHON_VERSION")
        status=0
        examples=Path(__file__).resolve().parent/"examples"
        if args.command=="schema":
            result={"ok":True,"command":"schema","version":VERSION,"schemas":INPUT_SCHEMA,
                "max_input_bytes_per_file":MAX_BYTES,"max_json_nesting":MAX_JSON_NESTING,
                "review_finding_codes":list(FINDINGS),
                "export_finding_codes":list(EXPORT_FINDINGS),"csv_columns":list(CSV_COLUMNS)}
        elif args.command=="onboard":
            result=onboard()
        elif args.command=="doctor":
            source,ss=load_json(examples/"source.json");candidates,cs=load_json(examples/"candidates.json")
            decisions,ds=load_json(examples/"decisions.json")
            checked=review(source,candidates,ss,cs);planned,data=export_plan(source,candidates,decisions,ss,cs,ds)
            if checked["summary"]!={"actions":5,"consistent":3,"needs_review":2} or not planned["ready"] or planned["accepted"]!=2 or planned["rejected"]!=3:
                raise InputError("SYNTHETIC_FIXTURE_INVALID")
            result={"ok":True,"command":"doctor","version":VERSION,
                "python":".".join(map(str,sys.version_info[:3])),"offline":True,
                "network_required":False,"auth_required":False,"runtime_dependencies":"Python 3.9+ standard library",
                "synthetic_fixture_found":True,"posix_installer":os.name=="posix"}
        else:
            paths=[examples/name for name in ("source.json","candidates.json","decisions.json")] if args.command=="demo" else [Path(args.source),Path(args.candidates)]
            if args.command=="export":
                paths.append(Path(args.decisions))
            source,ss=load_json(paths[0]);candidates,cs=load_json(paths[1])
            checked=review(source,candidates,ss,cs)
            if args.command=="review":
                result=checked;status=int(checked["summary"]["needs_review"]>0)
            else:
                decisions,ds=load_json(paths[2]);planned,data=export_plan(source,candidates,decisions,ss,cs,ds)
                if args.command=="demo" and args.replace and not args.output:
                    raise InputError("CLI_USAGE")
                if planned["ready"] and args.output:
                    write_output(args.output,data,paths,args.replace)
                status=0 if planned["ready"] else 1
                if args.command=="demo":
                    result={"ok":True,"command":"demo","version":VERSION,"synthetic":True,
                        "review":checked,"export":planned,"output_written":bool(planned["ready"] and args.output)}
                else:
                    result=planned
        emit(result)
        return status
    except (InputError,OSError,ValueError,TypeError,RecursionError,OverflowError) as error:
        emit({"ok":False,"error":{"code":str(error) if isinstance(error,InputError) else "OPERATION_REFUSED",
            "message":"Input, command or output was refused. See schema/help; supplied payloads are not included in errors."}})
        return 2


if __name__=="__main__":
    sys.exit(main())
