"""Tests for the bundled scripts.

None of these need a database, a model, or a BPMN modeller — which is the point.
The interesting failures in all three scripts live at the parser boundary, and a
boundary you can test in isolation is a boundary that stays correct.

Run:  pytest -q          (from the repository root)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def load(script_path: Path):
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_sql = load(SKILLS / "sql-safety-review" / "scripts" / "check_sql.py")
build_bpmn = load(SKILLS / "bpmn-from-prose" / "scripts" / "build_bpmn.py")
validate_extraction = load(SKILLS / "structured-extraction" / "scripts" / "validate_extraction.py")
lint_skill = load(SKILLS / "skill-doctor" / "scripts" / "lint_skill.py")


def verdict(sql: str, allow_write: bool = False) -> str:
    findings, _ = check_sql.check_with_sqlglot(sql, allow_write)
    return check_sql.verdict_of(findings)


# --------------------------------------------------------------------------- SQL
# These mirror the "cases worth having tests for" table in
# skills/sql-safety-review/references/postgres-patterns.md. If the table and these
# tests ever disagree, one of them is lying to the reader.

@pytest.mark.parametrize("sql", [
    "WITH t AS (DELETE FROM users RETURNING *) SELECT * FROM t",   # write hidden in a CTE
    "SELECT * INTO copy FROM users",                                # creates a table
    "SELECT 1; DROP TABLE users",                                   # payload is statement two
    "SET search_path = evil",                                       # changes what "users" means
    "SET search_path=evil",                                         # ... and without the spaces
    "SET SESSION statement_timeout = '5s'",
    "DELETE FROM sessions",                                         # no WHERE
    "TRUNCATE TABLE audit_log",
    "GRANT SELECT ON users TO PUBLIC",
])
def test_blocked(sql):
    assert verdict(sql) == "BLOCK", f"should be blocked: {sql}"


@pytest.mark.parametrize("sql", [
    "SELECT * FROM users WHERE id = 1",              # the control case
    "WITH t AS (SELECT 1) SELECT * FROM t",          # legitimate CTE
    "SELECT count(*) FROM events",                   # aggregate, not a scan
    "SELECT u.email FROM users u JOIN orders o ON o.user_id = u.id WHERE o.total > 100",
])
def test_accepted(sql):
    assert verdict(sql) == "OK", f"should pass cleanly: {sql}"


def test_distinct_inside_cte_is_not_flagged():
    """The correct fix for row multiplication must not be reported as a smell."""
    sql = ("WITH stale AS (SELECT DISTINCT user_id FROM sessions WHERE last_seen < now()) "
           "SELECT u.email FROM users u JOIN stale s ON s.user_id = u.id LIMIT 100")
    assert verdict(sql) == "OK"


def test_allow_write_still_blocks_unqualified_writes():
    assert verdict("UPDATE users SET active = false", allow_write=True) == "BLOCK"
    assert verdict("UPDATE users SET active = false WHERE id = 1", allow_write=True) == "OK"


def test_fallback_mode_is_marked_non_authoritative():
    findings, status = check_sql.check_fallback("SELECT 1", False)
    assert status == "fallback"
    assert any(f.code == "no_parser" for f in findings)


# -------------------------------------------------------------------------- BPMN

MINIMAL_SPEC = {
    "id": "p", "name": "P",
    "elements": [
        {"id": "start", "type": "startEvent", "name": "Zgłoszenie"},
        {"id": "t1", "type": "userTask", "name": "Obsługa zgłoszenia"},
        {"id": "g1", "type": "exclusiveGateway", "name": "Na gwarancji?"},
        {"id": "t2", "type": "userTask", "name": "Naprawa"},
        {"id": "end", "type": "endEvent", "name": "Zamknięte"},
    ],
    "flows": [
        {"from": "start", "to": "t1"}, {"from": "t1", "to": "g1"},
        {"from": "g1", "to": "t2", "name": "tak"}, {"from": "g1", "to": "end", "name": "nie"},
        {"from": "t2", "to": "end"},
    ],
}


def test_minimal_spec_validates_and_generates():
    assert build_bpmn.validate(MINIMAL_SPEC) == []
    xml = build_bpmn.build_xml(json.loads(json.dumps(MINIMAL_SPEC)))
    assert xml.startswith("<?xml")
    # DI is the part that decides whether a modeller shows a diagram or a blank canvas.
    assert xml.count("BPMNShape") >= len(MINIMAL_SPEC["elements"])
    assert xml.count("BPMNEdge") >= len(MINIMAL_SPEC["flows"])


def test_catch_event_without_kind_is_rejected():
    spec = json.loads(json.dumps(MINIMAL_SPEC))
    spec["elements"].insert(2, {"id": "w", "type": "intermediateCatchEvent", "name": "Czekamy"})
    spec["flows"] = [f for f in spec["flows"] if f != {"from": "t1", "to": "g1"}]
    spec["flows"] += [{"from": "t1", "to": "w"}, {"from": "w", "to": "g1"}]
    problems = build_bpmn.validate(spec)
    assert any("event" in p and "well-formed" in p for p in problems)


def test_catch_event_with_kind_emits_a_definition():
    spec = json.loads(json.dumps(MINIMAL_SPEC))
    spec["elements"].insert(2, {"id": "w", "type": "intermediateCatchEvent",
                                "name": "Czekamy", "event": "message"})
    spec["flows"] = [f for f in spec["flows"] if f != {"from": "t1", "to": "g1"}]
    spec["flows"] += [{"from": "t1", "to": "w"}, {"from": "w", "to": "g1"}]
    assert build_bpmn.validate(spec) == []
    assert "messageEventDefinition" in build_bpmn.build_xml(spec)


def test_unsupported_elements_are_refused_with_an_alternative():
    spec = json.loads(json.dumps(MINIMAL_SPEC))
    spec["elements"].append({"id": "b", "type": "boundaryEvent", "name": "Termin"})
    problems = build_bpmn.validate(spec)
    assert any("not supported" in p and "exclusive gateway" in p for p in problems)


def test_validator_catches_orphans_and_dead_ends():
    spec = json.loads(json.dumps(MINIMAL_SPEC))
    spec["elements"].append({"id": "orphan", "type": "userTask", "name": "Nikt tu nie trafia"})
    problems = build_bpmn.validate(spec)
    assert any("unreachable" in p for p in problems)
    assert any("dead end" in p for p in problems)


def test_layout_produces_no_overlaps():
    notes = build_bpmn.check_layout(MINIMAL_SPEC)
    assert not any(n.startswith("OVERLAP") for n in notes), notes


# -------------------------------------------------------------------- extraction

SCHEMA = json.loads((SKILLS / "structured-extraction" / "examples" /
                     "invoice.schema.json").read_text(encoding="utf-8"))


def test_polish_decimal_comma_is_normalised_not_truncated():
    """The failure this whole skill is built around: 123,45 must not become 123."""
    assert validate_extraction.normalise_number("1 234,56") == 1234.56
    assert validate_extraction.normalise_number("123,45") == 123.45
    assert validate_extraction.normalise_number("1.234,56") == 1234.56   # PL/DE grouping
    assert validate_extraction.normalise_number("1,234.56") == 1234.56   # US grouping
    assert validate_extraction.normalise_number("12 345,00 zł") == 12345.00


def test_dates_are_normalised_and_ambiguity_is_refused():
    assert validate_extraction.normalise_date("03.04.2026") == "2026-04-03"
    assert validate_extraction.normalise_date("2026-04-03") == "2026-04-03"
    assert validate_extraction.normalise_date("25/12/2026") == "2026-12-25"  # unambiguous
    with pytest.raises(ValueError):
        validate_extraction.normalise_date("03/04/2026", assume_day_first=False)
    with pytest.raises(ValueError):
        validate_extraction.normalise_date("2026-02-30")


def test_invented_field_fails_validation():
    record = {"counterparty": "Silky Coders", "amount": 100.0, "currency": "PLN",
              "due_date": "2026-04-03", "invoice_number": "FV/1", "vat_rate": 23}
    assert validate_extraction.validate_without_jsonschema(record, SCHEMA)


def test_unknown_currency_fails_validation():
    record = {"counterparty": "Silky Coders", "amount": 100.0, "currency": "GBP",
              "due_date": "2026-04-03", "invoice_number": "FV/1"}
    errors = validate_extraction.validate_without_jsonschema(record, SCHEMA)
    assert any("GBP" in e for e in errors)


def test_valid_record_passes():
    record = {"counterparty": "Silky Coders sp. z o.o.", "amount": 1234.56, "currency": "PLN",
              "due_date": "2026-04-03", "invoice_number": "FV/2026/08/117", "po_number": None}
    assert validate_extraction.validate_without_jsonschema(record, SCHEMA) == []


def test_code_fences_are_stripped():
    assert validate_extraction.strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_cli_exits_non_zero_on_a_bad_record():
    """The contract the workflow depends on: a bad record fails the step."""
    schema_path = SKILLS / "structured-extraction" / "examples" / "invoice.schema.json"
    bad = '{"counterparty": "X", "amount": 100, "currency": "GBP", ' \
          '"due_date": "2026-04-03", "invoice_number": "1"}'
    result = subprocess.run(
        [sys.executable,
         str(SKILLS / "structured-extraction" / "scripts" / "validate_extraction.py"),
         "--schema", str(schema_path)],
        input=bad, capture_output=True, text=True)
    assert result.returncode == 1
    assert "EXTRACTION FAILED" in result.stderr


# ------------------------------------------------------------------ skill-doctor

def test_every_skill_in_this_repo_lints_clean():
    """The linter is not much use if the repository it ships in fails it."""
    failures = []
    for directory in sorted(SKILLS.iterdir()):
        if not (directory / "SKILL.md").is_file():
            continue
        findings, name = lint_skill.lint(directory)
        errors = [f for f in findings if f.level == lint_skill.ERROR]
        warnings = [f for f in findings if f.level == lint_skill.WARN]
        if errors or warnings:
            failures.append((name, [f"{f.level} {f.rule}: {f.message}"
                                    for f in errors + warnings]))
    assert not failures, failures


def test_linter_flags_a_description_with_no_trigger_language(tmp_path):
    skill = tmp_path / "vague-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: vague-skill\ndescription: Helps with data processing and related tasks "
        "in a general sense for various purposes.\n---\n\n# Vague skill\n\n" + "Body. " * 60,
        encoding="utf-8")
    findings, _ = lint_skill.lint(skill)
    assert any(f.rule == "description-no-triggers" for f in findings)


def test_linter_flags_a_dead_reference(tmp_path):
    skill = tmp_path / "broken-refs"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: broken-refs\ndescription: Does a specific thing with files. Use this "
        "whenever someone needs that specific thing done to a file they name.\n---\n\n"
        "# Broken refs\n\nRun scripts/missing.py to do the thing. " + "Body. " * 40,
        encoding="utf-8")
    findings, _ = lint_skill.lint(skill)
    assert any(f.rule == "dead-reference" for f in findings)
