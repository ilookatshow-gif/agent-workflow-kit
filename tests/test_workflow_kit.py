import contextlib
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workflow_kit", ROOT/"workflow_kit.py")
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


def raw(value):
    return (json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode("utf-8")


def fixtures():
    return [json.loads((ROOT/"examples"/name).read_text(encoding="utf-8"))
            for name in ("source.json","candidates.json","decisions.json")]


def bound(source=None,candidates=None,decisions=None):
    originals=fixtures()
    source=originals[0] if source is None else source
    candidates=originals[1] if candidates is None else candidates
    decisions=originals[2] if decisions is None else decisions
    ss=kit.sha256(raw(source));candidates["source_sha256"]=ss
    cs=kit.sha256(raw(candidates));decisions.update(source_sha256=ss,candidates_sha256=cs)
    return source,candidates,decisions,ss,cs,kit.sha256(raw(decisions))


def checked(source=None,candidates=None):
    s,c,d,ss,cs,ds=bound(source,candidates)
    return kit.review(s,c,ss,cs)


def codes(source=None,candidates=None,index=0):
    return checked(source,candidates)["rows"][index]["findings"]


def plan(source=None,candidates=None,decisions=None):
    return kit.export_plan(*bound(source,candidates,decisions))


def csv_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def cli(*args,cwd=None,env=None):
    return subprocess.run([sys.executable,"-B",str(ROOT/"workflow_kit.py"),"--json",*map(str,args)],
                          cwd=cwd,env=env,capture_output=True,timeout=30)


class ReviewTests(unittest.TestCase):
    def test_original_five_candidate_interpretations(self):
        x=checked()
        self.assertEqual(x["summary"],{"actions":5,"consistent":3,"needs_review":2})
        self.assertEqual([r["findings"] for r in x["rows"]],[[],[],["QUOTE_MISMATCH"],["OWNER_SPEAKER_MISMATCH"],[]])

    def test_exact_question_is_not_automatic_commitment(self):
        x=checked();self.assertEqual(x["rows"][4]["classification"],"consistent")
        self.assertTrue(x["rows"][4]["quote"].endswith("?"))
        result,data=plan();self.assertNotIn("A05",[r["action_id"] for r in csv_rows(data)])
        self.assertEqual(result["accepted"],2)

    def test_source_hash_drift_is_visible_on_every_row(self):
        s,c,d,ss,cs,ds=bound();c["source_sha256"]="0"*64
        result=kit.review(s,c,ss,kit.sha256(raw(c)))
        self.assertTrue(all("SOURCE_HASH_MISMATCH" in r["findings"] for r in result["rows"]))

    def test_unknown_line_is_not_proof_of_real_absence(self):
        s,c,d=fixtures();c["actions"][0]["source_line_id"]="not-in-notes"
        self.assertEqual(codes(s,c),["LINE_NOT_FOUND"])

    def test_unknown_owner_and_wrong_speaker_are_both_visible(self):
        s,c,d=fixtures();c["actions"][0]["owner_id"]="unlisted"
        self.assertEqual(codes(s,c),["OWNER_NOT_FOUND","OWNER_SPEAKER_MISMATCH"])

    def test_wrong_known_speaker(self):
        s,c,d=fixtures();c["actions"][0]["owner_id"]="finance"
        self.assertEqual(codes(s,c),["OWNER_SPEAKER_MISMATCH"])

    def test_negative_reversed_and_past_end_spans_are_not_sliced(self):
        for start,end in [(-1,3),(3,3),(10,3),(0,10000)]:
            s,c,d=fixtures();c["actions"][0].update(start=start,end=end)
            self.assertEqual(codes(s,c),["SPAN_OUT_OF_RANGE"])

    def test_exact_mismatch(self):
        s,c,d=fixtures();c["actions"][0]["quote"]="Different supplied words"
        self.assertEqual(codes(s,c),["QUOTE_MISMATCH"])

    def test_offsets_are_unicode_codepoints_not_utf16(self):
        s,c,d=fixtures();original=s["lines"][0]["text"];s["lines"][0]["text"]="🙂"+original
        c["actions"][0].update(start=1,end=1+len(original))
        self.assertEqual(codes(s,c),[])
        c["actions"][0].update(start=2,end=2+len(original))
        self.assertEqual(codes(s,c),["SPAN_OUT_OF_RANGE"])

    def test_source_and_candidate_meeting_identity_must_match(self):
        s,c,d=fixtures();c["meeting_id"]="other"
        with self.assertRaisesRegex(kit.InputError,"MEETING_ID_MISMATCH"):
            checked(s,c)

    def test_scope_is_supplied_spans_not_extraction_completeness(self):
        x=checked();self.assertEqual(x["evidence_basis"],"supplied_note_spans_only")
        self.assertEqual(len(x["rows"]),5)
        self.assertEqual(len(fixtures()[0]["lines"]),6)
        self.assertNotIn("complete",x)


class ValidationTests(unittest.TestCase):
    def test_unknown_source_speaker_refused(self):
        s,c,d=fixtures();s["lines"][0]["speaker_id"]="unknown"
        with self.assertRaisesRegex(kit.InputError,"SOURCE_SPEAKER_UNKNOWN"):
            kit.validate_source(s)

    def test_duplicate_participant_and_line_ids_refused(self):
        for field in ["participants","lines"]:
            s,c,d=fixtures();s[field].append(copy.deepcopy(s[field][0]))
            with self.assertRaisesRegex(kit.InputError,"DUPLICATE_ID"):
                kit.validate_source(s)

    def test_duplicate_action_ids_refused(self):
        s,c,d=fixtures();c["actions"].append(copy.deepcopy(c["actions"][0]))
        with self.assertRaisesRegex(kit.InputError,"DUPLICATE_ID"):
            kit.validate_candidates(c)

    def test_empty_extraction_is_not_a_completed_batch(self):
        s,c,d=fixtures();c["actions"]=[]
        with self.assertRaisesRegex(kit.InputError,"COLLECTION_INVALID"):
            kit.validate_candidates(c)

    def test_actual_calendar_dates_only(self):
        s,c,d=fixtures();c["actions"][0]["due_date"]="2028-02-29";kit.validate_candidates(c)
        for value in ["2026-02-29","2026-13-01","2026-1-1","0000-01-01","20261113",5]:
            c["actions"][0]["due_date"]=value
            with self.assertRaisesRegex(kit.InputError,"DATE_INVALID"):
                kit.validate_candidates(c)

    def test_bool_is_not_version_or_span_integer(self):
        s,c,d=fixtures();s["schema_version"]=True
        with self.assertRaisesRegex(kit.InputError,"SCHEMA_VERSION_INVALID"):
            kit.validate_source(s)
        for field in ["start","end"]:
            s,c,d=fixtures();c["actions"][0][field]=True
            with self.assertRaisesRegex(kit.InputError,"SPAN_INTEGER_INVALID"):
                kit.validate_candidates(c)

    def test_exact_fields_across_three_inputs(self):
        for index,validator in [(0,kit.validate_source),(1,kit.validate_candidates)]:
            items=fixtures();items[index]["unexpected"]=1
            with self.assertRaisesRegex(kit.InputError,"OBJECT_FIELDS_INVALID"):
                validator(items[index])
        s,c,d=fixtures();d["unexpected"]=1
        with self.assertRaisesRegex(kit.InputError,"OBJECT_FIELDS_INVALID"):
            kit.validate_decisions(d,c)

    def test_blank_control_and_surrogate_text_are_not_truncated(self):
        for value in [" ","private\nline","\ud800","x"*4001]:
            s,c,d=fixtures();s["lines"][0]["text"]=value
            with self.assertRaisesRegex(kit.InputError,"STRING_INVALID"):
                kit.validate_source(s)

    def test_bounds_on_each_collection(self):
        s,c,d=fixtures();s["participants"]=s["participants"][:1]*101
        with self.assertRaisesRegex(kit.InputError,"COLLECTION_INVALID"):
            kit.validate_source(s)
        s,c,d=fixtures();c["actions"]=c["actions"][:1]*501
        with self.assertRaisesRegex(kit.InputError,"COLLECTION_INVALID"):
            kit.validate_candidates(c)

    def test_duplicate_json_keys_even_nested_refused(self):
        for data in [b'{"x":1,"x":2}',b'{"nested":{"x":1,"x":2}}']:
            with self.assertRaisesRegex(kit.InputError,"DUPLICATE_JSON_KEY"):
                kit.parse_json(data)

    def test_json_utf8_size_and_depth_limits(self):
        for data in [b'\xff',b'[] trailing',b'['*2000+b']'*2000]:
            with self.assertRaises(kit.InputError):kit.parse_json(data)
        with self.assertRaisesRegex(kit.InputError,"INPUT_TOO_LARGE"):
            kit.parse_json(b' '* (kit.MAX_BYTES+1))

    def test_nonfinite_and_oversized_integer_tokens_refused(self):
        for data in [b'NaN',b'Infinity',b'-Infinity',b'1e999']:
            with self.assertRaisesRegex(kit.InputError,"NONFINITE_JSON"):
                kit.parse_json(data)
        with self.assertRaisesRegex(kit.InputError,"INTEGER_TOO_LARGE"):
            kit.parse_json(b'9'*10000)

    def test_malformed_hash_identifier_and_nonstring_decision(self):
        s,c,d=fixtures();c["source_sha256"]="A"*64
        with self.assertRaisesRegex(kit.InputError,"HASH_INVALID"):kit.validate_candidates(c)
        s,c,d=fixtures();c["actions"][0]["id"]="../unsafe"
        with self.assertRaisesRegex(kit.InputError,"IDENTIFIER_INVALID"):kit.validate_candidates(c)
        s,c,d=fixtures();d["decisions"][0]["decision"]={}
        with self.assertRaisesRegex(kit.InputError,"DECISION_INVALID"):kit.validate_decisions(d,c)


class ExportTests(unittest.TestCase):
    def test_two_reviewed_actions_preserve_owner_order_and_unknown_due(self):
        result,data=plan();rows=csv_rows(data)
        self.assertTrue(result["ready"]);self.assertEqual(result["accepted"],2);self.assertEqual(result["rejected"],3)
        self.assertEqual([r["action_id"] for r in rows],["A01","A02"])
        self.assertEqual([r["owner_id"] for r in rows],["ops","finance"])
        self.assertEqual([r["due_date"] for r in rows],["2026-11-13",""])
        self.assertEqual(result["output_sha256"],hashlib.sha256(data).hexdigest())
        self.assertNotIn(b'\r\n',data);self.assertEqual(result["output_bytes"],len(data))

    def test_decision_hash_drift_blocks_whole_export(self):
        for field,code in [("source_sha256","REVIEW_SOURCE_HASH_MISMATCH"),("candidates_sha256","REVIEW_CANDIDATES_HASH_MISMATCH")]:
            s,c,d,ss,cs,ds=bound();d[field]="0"*64
            result,data=kit.export_plan(s,c,d,ss,cs,kit.sha256(raw(d)))
            self.assertFalse(result["ready"]);self.assertIsNone(data)
            self.assertIn(code,[x["code"] for x in result["findings"]])
            self.assertEqual(result["exported_actions"],0)

    def test_missing_decision_blocks_no_partial_register(self):
        s,c,d=fixtures();d["decisions"].pop()
        result,data=plan(s,c,d)
        self.assertIsNone(data);self.assertEqual(result["findings"],[{"code":"DECISION_MISSING","action_id":"A05"}])

    def test_one_accepted_bad_citation_blocks_even_other_good_actions(self):
        for action_id in ["A03","A04"]:
            s,c,d=fixtures();next(x for x in d["decisions"] if x["action_id"]==action_id)["decision"]="accept"
            result,data=plan(s,c,d);self.assertIsNone(data)
            self.assertFalse(result["ready"]);self.assertEqual(result["findings"][0]["code"],"ACCEPTED_ACTION_INVALID")
            self.assertEqual(result["exported_actions"],0)

    def test_explicit_bad_rejections_are_omitted_and_counted(self):
        result,data=plan();self.assertEqual(result["rejected"],3)
        self.assertEqual(len(csv_rows(data)),2)
        self.assertNotIn("Финальный файл уже отправлен",data.decode("utf-8"))

    def test_all_rejected_is_explicit_header_only(self):
        s,c,d=fixtures()
        for row in d["decisions"]:row.update(decision="reject",reason="Rejected after supplied review")
        result,data=plan(s,c,d)
        self.assertTrue(result["ready"]);self.assertEqual(result["accepted"],0);self.assertEqual(result["rejected"],5)
        self.assertEqual(data,("|".join(kit.CSV_COLUMNS).replace("|",",")+"\n").encode())
        self.assertEqual(csv_rows(data),[])

    def test_accepted_row_order_follows_candidates_not_decision_order(self):
        s,c,d=fixtures();c["actions"]=list(reversed(c["actions"]));d["decisions"]=list(reversed(d["decisions"]))
        result,data=plan(s,c,d);self.assertEqual([r["action_id"] for r in csv_rows(data)],["A02","A01"])

    def test_unknown_duplicate_and_blank_reject_decisions_refused(self):
        for mutation,code in [(lambda d:d["decisions"][0].update(action_id="unknown"),"DECISION_ACTION_UNKNOWN"),
                (lambda d:d["decisions"].append(copy.deepcopy(d["decisions"][0])),"DUPLICATE_ID"),
                (lambda d:d["decisions"][2].update(reason=" "),"STRING_INVALID")]:
            s,c,d=fixtures();mutation(d)
            with self.assertRaisesRegex(kit.InputError,code):kit.validate_decisions(d,c)

    def test_review_identity_and_date_are_supplied_not_authenticated(self):
        s,c,d=fixtures();d.update(reviewer_id="unverified-reviewer",reviewed_on="2099-01-01")
        result,data=plan(s,c,d);self.assertTrue(result["reviewer_declared"])
        self.assertEqual(result["reviewed_on"],"2099-01-01");self.assertNotIn("authenticated",result)

    def test_review_meeting_mismatch_refused(self):
        s,c,d=fixtures();d["meeting_id"]="other"
        with self.assertRaisesRegex(kit.InputError,"MEETING_ID_MISMATCH"):plan(s,c,d)

    def test_semantic_question_is_not_judged_by_checker(self):
        s,c,d=fixtures();d["decisions"][4].update(decision="accept",reason="Supplied reviewer claim, not verified meaning")
        result,data=plan(s,c,d)
        self.assertTrue(result["ready"]);self.assertEqual(result["accepted"],3)
        self.assertIn("A05",[r["action_id"] for r in csv_rows(data)])

    def test_csv_unicode_comma_and_quote_roundtrip(self):
        s,c,d=fixtures();c["actions"][0]["title"]='План, версия "А" 🙂'
        result,data=plan(s,c,d);self.assertEqual(csv_rows(data)[0]["title"],c["actions"][0]["title"])
        self.assertIn('"План, версия ""А"" 🙂"',data.decode("utf-8"))

    def test_formula_mitigation_covers_each_declared_prefix_and_whitespace(self):
        for value in ["=SUM(A1)","+cmd","-formula","@ref","   =x","\u00a0+x"]:
            self.assertEqual(kit.safe_cell(value),("'"+value,True))
        self.assertEqual(kit.safe_cell("plain = text"),("plain = text",False))

    def test_formula_cells_transformed_without_changing_original_json(self):
        s,c,d=fixtures();s["participants"][0]["label"]="@owner";s["lines"][0]["text"]="=source"
        c["actions"][0].update(title=" +formula",quote="=source",start=0,end=7)
        before=raw(s);result,data=plan(s,c,d);rows=csv_rows(data)
        self.assertEqual(raw(s),before);self.assertEqual(result["formula_escaped_cells"],3)
        self.assertEqual(rows[0]["quote"],"'=source");self.assertEqual(rows[0]["title"],"' +formula")


class CommandTests(unittest.TestCase):
    def test_doctor_schema_and_demo_are_offline(self):
        for command in ["doctor","schema","demo"]:
            cp=cli(command);self.assertEqual(cp.returncode,0,cp.stderr)
            result=json.loads(cp.stdout);self.assertTrue(result["ok"])
            self.assertNotIn(b'\r\n',cp.stdout)
        result=json.loads(cli("doctor").stdout);self.assertFalse(result["auth_required"]);self.assertFalse(result["network_required"])

    def test_demo_without_output_is_preview_only_from_foreign_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();before=list(root.iterdir());cp=cli("demo",cwd=str(root))
            self.assertEqual(cp.returncode,0);self.assertFalse(json.loads(cp.stdout)["output_written"])
            self.assertEqual(list(root.iterdir()),before)

    def test_actual_review_exit_one_and_all_rows_present(self):
        cp=cli("review",ROOT/"examples/source.json",ROOT/"examples/candidates.json")
        self.assertEqual(cp.returncode,1);self.assertEqual(json.loads(cp.stdout)["summary"]["actions"],5)

    def test_actual_demo_and_export_csv_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();a=root/"demo.csv";b=root/"export.csv"
            cp=cli("demo","--output",a,cwd=str(root));self.assertEqual(cp.returncode,0)
            result=json.loads(cp.stdout);self.assertTrue(result["output_written"])
            cp=cli("export",*(ROOT/"examples"/n for n in ["source.json","candidates.json","decisions.json"]),"--output",b)
            self.assertEqual(cp.returncode,0);self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(json.loads(cp.stdout)["output_sha256"],kit.sha256(b.read_bytes()))

    def test_no_overwrite_explicit_replace_and_no_input_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();target=root/"tasks.csv";target.write_bytes(b"keep")
            cp=cli("demo","--output",target);self.assertEqual(cp.returncode,2);self.assertEqual(target.read_bytes(),b"keep")
            self.assertEqual(cli("demo","--output",target,"--replace").returncode,0)
            cp=cli("demo","--output",ROOT/"examples/source.json","--replace")
            self.assertEqual(cp.returncode,2);self.assertEqual(json.loads(cp.stdout)["error"]["code"],"OUTPUT_IS_INPUT")

    @unittest.skipUnless(os.name=="posix","POSIX filesystem alias checks")
    def test_output_hardlink_and_symlink_preserve_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();original=ROOT/"examples/source.json";before=original.read_bytes()
            hard=root/"hard.json";os.link(str(original),str(hard))
            cp=cli("demo","--output",hard,"--replace");self.assertEqual(cp.returncode,2)
            self.assertEqual(json.loads(cp.stdout)["error"]["code"],"OUTPUT_IS_INPUT")
            link=root/"link.csv";link.symlink_to(original)
            self.assertEqual(cli("demo","--output",link,"--replace").returncode,2)
            self.assertEqual(original.read_bytes(),before)

    def test_invalid_private_payload_does_not_leak_or_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();invalid=root/"input.json";invalid.write_bytes(b'{"PRIVATE-DO-NOT-ECHO":"value"}')
            output=root/"out.csv";cp=cli("export",invalid,ROOT/"examples/candidates.json",ROOT/"examples/decisions.json","--output",output)
            self.assertEqual(cp.returncode,2);self.assertFalse(output.exists())
            self.assertNotIn(b"PRIVATE-DO-NOT-ECHO",cp.stdout+cp.stderr);self.assertNotIn(b"Traceback",cp.stdout+cp.stderr)

    def test_missing_decision_returns_one_and_leaves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();decisions=fixtures()[2];decisions["decisions"].pop()
            decision_file=root/"decisions.json";decision_file.write_bytes(raw(decisions));output=root/"out.csv";output.write_bytes(b"keep")
            cp=cli("export",ROOT/"examples/source.json",ROOT/"examples/candidates.json",decision_file,"--output",output,"--replace")
            self.assertEqual(cp.returncode,1);self.assertFalse(json.loads(cp.stdout)["ready"]);self.assertEqual(output.read_bytes(),b"keep")

    def test_raw_candidate_whitespace_requires_a_new_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();candidate=root/"candidates.json";candidate.write_bytes((ROOT/"examples/candidates.json").read_bytes()+b" ")
            output=root/"out.csv";cp=cli("export",ROOT/"examples/source.json",candidate,ROOT/"examples/decisions.json","--output",output)
            self.assertEqual(cp.returncode,1);self.assertFalse(output.exists())
            self.assertIn("REVIEW_CANDIDATES_HASH_MISMATCH",[x["code"] for x in json.loads(cp.stdout)["findings"]])

    def test_directory_input_and_replace_without_output_refused(self):
        self.assertEqual(cli("review",ROOT,ROOT/"examples/candidates.json").returncode,2)
        self.assertEqual(cli("demo","--replace").returncode,2)

    def test_windows_newline_translation_cannot_change_json_bytes(self):
        buffer=io.BytesIO();wrapper=io.TextIOWrapper(buffer,encoding="cp1252",newline="\r\n")
        value={"ok":True,"text":"Русский 🙂"}
        with contextlib.redirect_stdout(wrapper):kit.emit(value)
        self.assertEqual(buffer.getvalue(),kit.json_bytes(value));wrapper.detach()

    def test_ascii_json_survives_legacy_stdout_encoding(self):
        cp=cli("demo",env=dict(os.environ,PYTHONIOENCODING="cp1252",PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(cp.returncode,0);x=json.loads(cp.stdout)
        self.assertEqual(x["review"]["rows"][0]["title"],"Подготовить черновик плана")
        self.assertTrue(all(b<128 for b in cp.stdout))

    def test_text_capture_fallback_and_error_json_lf(self):
        capture=io.StringIO()
        with contextlib.redirect_stdout(capture):
            code=kit.main(["--json","invalid-private-command"])
        self.assertEqual(code,2);self.assertEqual(json.loads(capture.getvalue())["error"]["code"],"CLI_USAGE")
        self.assertNotIn("invalid-private-command",capture.getvalue());self.assertNotIn("\r\n",capture.getvalue())

    def test_optional_onboard_once_and_bad_marker_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();runtime=root/"workflow_kit.py";shutil.copyfile(ROOT/"workflow_kit.py",runtime)
            args=[sys.executable,"-B",str(runtime),"--json","onboard"]
            first=subprocess.run(args,capture_output=True);second=subprocess.run(args,capture_output=True)
            self.assertEqual(first.returncode,0);self.assertFalse(json.loads(first.stdout)["already_shown"])
            self.assertTrue(json.loads(second.stdout)["already_shown"])
            (root/".onboarded").write_bytes(b"modified")
            failed=subprocess.run(args,capture_output=True);self.assertEqual(failed.returncode,2)


@unittest.skipUnless(os.name=="posix","Native installer is POSIX only")
class InstallTests(unittest.TestCase):
    def test_clean_foreign_install_demo_and_precise_uninstall(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();prefix=root/"installed";binary_dir=root/"bin";foreign=root/"foreign";foreign.mkdir()
            cp=subprocess.run([sys.executable,"-B",str(ROOT/"install.py"),"--prefix",str(prefix),"--bin-dir",str(binary_dir)],cwd=str(foreign),capture_output=True)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            executable=binary_dir/"agent-workflow-kit";env=dict(os.environ,PYTHONIOENCODING="cp1252",PYTHONDONTWRITEBYTECODE="1")
            cp=subprocess.run([str(executable),"--json","demo","--output",str(foreign/"tasks.csv")],cwd=str(foreign),env=env,capture_output=True)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr);self.assertEqual(len(csv_rows((foreign/"tasks.csv").read_bytes())),2)
            subprocess.run([str(executable),"--json","onboard"],capture_output=True,check=True)
            user=prefix/"user-notes.txt";user.write_bytes(b"preserve")
            cp=subprocess.run([sys.executable,"-B",str(prefix/"uninstall.py"),"--prefix",str(prefix),"--bin-dir",str(binary_dir)],cwd=str(foreign),capture_output=True)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr);self.assertEqual(user.read_bytes(),b"preserve");self.assertFalse(executable.exists())

    def test_modified_installation_is_not_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();prefix=root/"installed";binary_dir=root/"bin"
            cp=subprocess.run([sys.executable,"-B",str(ROOT/"install.py"),"--prefix",str(prefix),"--bin-dir",str(binary_dir)],capture_output=True)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            (prefix/"workflow_kit.py").write_bytes(b"user-modified")
            cp=subprocess.run([sys.executable,"-B",str(prefix/"uninstall.py"),"--prefix",str(prefix),"--bin-dir",str(binary_dir)],capture_output=True)
            self.assertEqual(cp.returncode,2);self.assertEqual((prefix/"workflow_kit.py").read_bytes(),b"user-modified")
            self.assertTrue((binary_dir/"agent-workflow-kit").exists())

    def test_installer_preserves_existing_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();prefix=root/"new";binary=root/"bin";binary.mkdir();target=binary/"agent-workflow-kit";target.write_bytes(b"keep")
            cp=subprocess.run([sys.executable,"-B",str(ROOT/"install.py"),"--prefix",str(prefix),"--bin-dir",str(binary)],capture_output=True)
            self.assertEqual(cp.returncode,2);self.assertEqual(target.read_bytes(),b"keep");self.assertFalse(prefix.exists())


if __name__=="__main__":
    unittest.main()
