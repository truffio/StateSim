"""Unit tests for tools/make_report.py using synthetic junit XML and requirements CSV."""

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "make_report.py"
_spec = importlib.util.spec_from_file_location("make_report", _TOOL)
mr = importlib.util.module_from_spec(_spec)
sys.modules["make_report"] = mr  # dataclasses look the module up by name
_spec.loader.exec_module(mr)


JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="6">
    <testcase classname="tests.unit.test_a" name="test_ok" time="0.01">
      <properties><property name="req" value="REQ-001"/></properties>
    </testcase>
    <testcase classname="tests.unit.test_a" name="test_fails" time="0.01">
      <properties><property name="req" value="REQ-002"/></properties>
      <failure message="assert 1 == 2">Traceback...
E   assert 1 == 2</failure>
    </testcase>
    <testcase classname="tests.unit.test_b" name="test_errors">
      <error message="fixture boom">setup traceback</error>
    </testcase>
    <testcase classname="tests.unit.test_b" name="test_skipped">
      <properties><property name="req" value="REQ-002"/></properties>
      <skipped message="not on windows" type="pytest.skip">skip</skipped>
    </testcase>
    <testcase classname="tests.requirements.test_req" name="test_multi" file="tests/requirements/test_req.py">
      <properties>
        <property name="req" value="REQ-003"/>
        <property name="req" value="REQ-004"/>
      </properties>
    </testcase>
    <testcase classname="tests.unit.test_c" name="test_orphan"/>
  </testsuite>
</testsuites>
"""

REQS_CSV = """req_id,area,requirement,spec_path,verification
REQ-001,master,"Loads a CSV, with comma",spec.a,unit_test
REQ-002,master,Second requirement,spec.b,unit_test
REQ-003,scope,Third requirement | with pipe,spec.c,use_case_test
REQ-004,scope,Fourth requirement,spec.d,unit_test
REQ-005,scope,Reviewed by a human,spec.e,review
REQ-006,scope,Static only,spec.f,static_check
REQ-007,scope,Untested unit requirement,spec.g,unit_test
"""


# ---------------------------------------------------------------- junit parsing

def test_parse_junit_outcomes_and_messages():
    tests = mr.parse_junit_text(JUNIT)
    by_name = {t.name: t for t in tests}
    assert [t.name for t in tests] == [
        "test_ok", "test_fails", "test_errors", "test_skipped", "test_multi", "test_orphan",
    ]
    assert by_name["test_ok"].outcome == mr.PASS
    assert by_name["test_fails"].outcome == mr.FAIL
    assert by_name["test_fails"].message == "assert 1 == 2"
    assert "E   assert 1 == 2" in by_name["test_fails"].details
    assert by_name["test_errors"].outcome == mr.ERROR
    assert by_name["test_errors"].message == "fixture boom"
    assert by_name["test_skipped"].outcome == mr.SKIP
    assert by_name["test_orphan"].outcome == mr.PASS


def test_parse_junit_reads_req_properties_in_order():
    by_name = {t.name: t for t in mr.parse_junit_text(JUNIT)}
    assert by_name["test_ok"].req_ids == ["REQ-001"]
    assert by_name["test_multi"].req_ids == ["REQ-003", "REQ-004"]
    assert by_name["test_orphan"].req_ids == []


def test_parse_junit_accepts_bytes_and_single_testsuite_root():
    xml = b'<testsuite><testcase classname="x" name="t"/></testsuite>'
    tests = mr.parse_junit_text(xml)
    assert len(tests) == 1 and tests[0].outcome == mr.PASS


def test_load_junit_from_file(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text(JUNIT, encoding="utf-8")
    assert len(mr.load_junit(path)) == 6


def test_node_id():
    t = mr.TestResult(classname="tests.unit.test_a", name="test_ok", outcome=mr.PASS)
    assert t.node_id == "tests.unit.test_a::test_ok"


# ---------------------------------------------------------------- classification

@pytest.mark.parametrize(
    "classname, file, expected",
    [
        ("tests.requirements.test_req", "", mr.CATEGORY_REQ),
        ("tests.unit.test_a", "tests/requirements/test_a.py", mr.CATEGORY_REQ),
        ("tests.unit.test_a", "tests\\requirements\\test_a.py", mr.CATEGORY_REQ),
        ("tests.unit.test_a", "", mr.CATEGORY_UNIT),
        ("tests.unit.test_trace", "tests/unit/test_trace.py", mr.CATEGORY_UNIT),
    ],
)
def test_classify(classname, file, expected):
    t = mr.TestResult(classname=classname, name="t", outcome=mr.PASS, file=file)
    assert mr.classify(t) == expected


# ---------------------------------------------------------------- requirements parsing

def test_parse_requirements_handles_quoted_commas_and_strips_fields():
    reqs = mr.parse_requirements_text(REQS_CSV)
    assert len(reqs) == 7
    assert reqs[0] == mr.Requirement("REQ-001", "master", "Loads a CSV, with comma", "spec.a", "unit_test")
    assert reqs[2].requirement == "Third requirement | with pipe"


def test_parse_requirements_skips_blank_ids_and_strips_whitespace():
    text = "req_id,area,requirement,spec_path,verification\n  REQ-9 , a , r , s , review\n,,,,\n"
    reqs = mr.parse_requirements_text(text)
    assert [r.req_id for r in reqs] == ["REQ-9"]
    assert reqs[0].area == "a"


def test_parse_requirements_missing_column_raises():
    with pytest.raises(ValueError, match="verification"):
        mr.parse_requirements_text("req_id,area,requirement,spec_path\nREQ-1,a,r,s\n")


def test_load_requirements_with_bom(tmp_path):
    path = tmp_path / "requirements.csv"
    path.write_text(REQS_CSV, encoding="utf-8-sig")
    assert mr.load_requirements(path)[0].req_id == "REQ-001"


# ---------------------------------------------------------------- model / statuses

def _model():
    return mr.build_report(mr.parse_junit_text(JUNIT), mr.parse_requirements_text(REQS_CSV))


def test_summary_counts_split_unit_and_requirement():
    summary = _model().summary
    assert summary["unit"] == {"pass": 2, "fail": 1, "error": 1, "skip": 1, "total": 5}
    assert summary["requirement"] == {"pass": 1, "fail": 0, "error": 0, "skip": 0, "total": 1}
    assert summary["total"] == {"pass": 3, "fail": 1, "error": 1, "skip": 1, "total": 6}


def test_requirement_statuses():
    statuses = {r.requirement.req_id: r.status for r in _model().rows}
    assert statuses["REQ-001"] == mr.STATUS_PASS
    assert statuses["REQ-002"] == mr.STATUS_FAIL          # one fail, one skip -> FAIL
    assert statuses["REQ-003"] == mr.STATUS_PASS          # multi-linked test passes
    assert statuses["REQ-004"] == mr.STATUS_PASS
    assert statuses["REQ-005"] == mr.STATUS_NOT_AUTOMATED  # review, no tests
    assert statuses["REQ-006"] == mr.STATUS_UNTESTED       # static_check, no tests
    assert statuses["REQ-007"] == mr.STATUS_UNTESTED       # unit_test, no tests


def test_skip_only_requirement_is_skip():
    tests = [mr.TestResult("tests.unit.x", "t", mr.SKIP, req_ids=["REQ-1"])]
    reqs = [mr.Requirement("REQ-1", "a", "r", "s", "unit_test")]
    assert mr.build_report(tests, reqs).rows[0].status == mr.STATUS_SKIP


def test_failures_and_orphans():
    model = _model()
    assert [t.name for t in model.failures] == ["test_fails", "test_errors"]
    assert [t.name for t in model.orphans] == ["test_errors", "test_orphan"]


def test_unknown_req_ids_reported():
    tests = [mr.TestResult("tests.unit.x", "t", mr.PASS, req_ids=["REQ-999"])]
    model = mr.build_report(tests, [])
    assert model.unknown_req_ids == {"REQ-999": ["tests.unit.x::t"]}


# ---------------------------------------------------------------- rendering

def test_render_markdown_sections_and_content():
    md = mr.render_markdown(_model())
    assert "## 1. Summary" in md
    assert "| Unit | 5 | 2 | 1 | 1 | 1 |" in md
    assert "| Requirement | 1 | 1 | 0 | 0 | 0 |" in md
    assert "## 2. Failures" in md
    assert "assert 1 == 2" in md
    assert "## 3. Requirement traceability matrix" in md
    assert "**UNTESTED**" in md
    assert "NOT-AUTOMATED" in md
    assert "## 4. Orphan tests" in md
    assert "`tests.unit.test_c::test_orphan`" in md


def test_render_markdown_escapes_pipes_in_table():
    md = mr.render_markdown(_model())
    assert "Third requirement \\| with pipe" in md


def test_render_markdown_no_failures_and_no_orphans():
    tests = [mr.TestResult("tests.unit.x", "t", mr.PASS, req_ids=["REQ-1"])]
    reqs = [mr.Requirement("REQ-1", "a", "r", "s", "unit_test")]
    md = mr.render_markdown(mr.build_report(tests, reqs))
    assert "No failures or errors." in md
    assert "None." in md


def test_render_html_is_escaped_and_complete():
    tests = [
        mr.TestResult("tests.unit.<x>", "t", mr.FAIL, message="a < b & c",
                      details="<script>boom</script>", req_ids=["REQ-1"])
    ]
    reqs = [mr.Requirement("REQ-1", "a", "needs <b>", "s", "unit_test")]
    page = mr.render_html(mr.build_report(tests, reqs))
    assert page.startswith("<!doctype html>")
    assert "<script>boom</script>" not in page
    assert "&lt;script&gt;boom&lt;/script&gt;" in page
    assert "needs &lt;b&gt;" in page
    assert "a &lt; b &amp; c" in page
    assert '<td class="status-UNTESTED">' not in page
    assert '<td class="status-FAIL">' in page
    assert "Requirement traceability matrix" in page


# ---------------------------------------------------------------- CLI

def test_main_writes_markdown_and_html(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT, encoding="utf-8")
    reqs = tmp_path / "requirements.csv"
    reqs.write_text(REQS_CSV, encoding="utf-8")
    out = tmp_path / "sub" / "report.md"
    html = tmp_path / "sub" / "report.html"

    rc = mr.main(["--junit", str(junit), "--requirements", str(reqs),
                  "--out", str(out), "--html", str(html)])
    assert rc == 0
    assert "## 3. Requirement traceability matrix" in out.read_text(encoding="utf-8")
    assert "<html" in html.read_text(encoding="utf-8")


def test_main_without_html_writes_only_markdown(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT, encoding="utf-8")
    reqs = tmp_path / "requirements.csv"
    reqs.write_text(REQS_CSV, encoding="utf-8")
    out = tmp_path / "report.md"
    assert mr.main(["--junit", str(junit), "--requirements", str(reqs), "--out", str(out)]) == 0
    assert out.exists()
    assert not list(tmp_path.glob("*.html"))


def test_main_missing_junit_returns_error(tmp_path):
    reqs = tmp_path / "requirements.csv"
    reqs.write_text(REQS_CSV, encoding="utf-8")
    rc = mr.main(["--junit", str(tmp_path / "nope.xml"), "--requirements", str(reqs),
                  "--out", str(tmp_path / "r.md")])
    assert rc == 2
