#!/usr/bin/env python3
"""Build a test report (Markdown, optional single-file HTML) from a pytest junit XML
and the requirements CSV.

Stdlib only. Usage:

    python tools/make_report.py [--junit reports/junit.xml]
                                [--requirements docs/requirements.csv]
                                [--out reports/test_report.md]
                                [--html reports/test_report.html]

Test cases link to requirements through junit properties:

    <testcase classname="tests.requirements.test_x" name="test_y">
      <properties><property name="req" value="REQ-001"/></properties>
    </testcase>

A test is a 'requirement' test when its classname or file path contains
'requirements'; otherwise it is a 'unit' test.
"""

from __future__ import annotations

import argparse
import csv
import html as html_lib
import io
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PASS, FAIL, ERROR, SKIP = "pass", "fail", "error", "skip"
OUTCOMES = (PASS, FAIL, ERROR, SKIP)
CATEGORY_UNIT = "unit"
CATEGORY_REQ = "requirement"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"
STATUS_UNTESTED = "UNTESTED"
STATUS_NOT_AUTOMATED = "NOT-AUTOMATED"
STATUSES = (STATUS_PASS, STATUS_FAIL, STATUS_UNTESTED, STATUS_NOT_AUTOMATED, STATUS_SKIP)

REQUIRED_COLUMNS = ("req_id", "area", "requirement", "spec_path", "verification")


@dataclass
class TestResult:
    classname: str
    name: str
    outcome: str  # one of OUTCOMES
    message: str = ""
    details: str = ""
    req_ids: list[str] = field(default_factory=list)
    file: str = ""

    @property
    def category(self) -> str:
        return classify(self)

    @property
    def node_id(self) -> str:
        return f"{self.classname}::{self.name}" if self.classname else self.name


@dataclass
class Requirement:
    req_id: str
    area: str
    requirement: str
    spec_path: str
    verification: str


@dataclass
class ReqRow:
    requirement: Requirement
    tests: list[TestResult]
    status: str


@dataclass
class ReportModel:
    summary: dict
    failures: list[TestResult]
    rows: list[ReqRow]
    orphans: list[TestResult]
    unknown_req_ids: dict[str, list[str]]


# ---------------------------------------------------------------- parsing

def classify(test: TestResult) -> str:
    """Return 'requirement' if the classname or file path mentions 'requirements', else 'unit'."""
    haystack = f"{test.classname} {test.file}".replace("\\", "/").lower()
    return CATEGORY_REQ if "requirements" in haystack else CATEGORY_UNIT


def _split_req_values(value: str) -> list[str]:
    parts = value.replace(";", ",").replace(" ", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def parse_junit_text(text: str | bytes) -> list[TestResult]:
    """Parse junit XML content into TestResult objects (in document order)."""
    root = ET.fromstring(text)
    results: list[TestResult] = []
    for tc in root.iter("testcase"):
        outcome = PASS
        message = ""
        details = ""
        for child in tc:
            tag = child.tag
            if tag in ("failure", "error", "skipped"):
                outcome = {"failure": FAIL, "error": ERROR, "skipped": SKIP}[tag]
                if tag != "skipped":
                    text_body = (child.text or "").strip()
                    details = text_body
                    message = child.get("message", "") or next(
                        (ln.strip() for ln in text_body.splitlines() if ln.strip()), ""
                    )
                else:
                    message = child.get("message", "") or ""
                break

        req_ids: list[str] = []
        for prop in tc.iter("property"):
            if prop.get("name") == "req" and prop.get("value"):
                for rid in _split_req_values(prop.get("value", "")):
                    if rid not in req_ids:
                        req_ids.append(rid)

        results.append(
            TestResult(
                classname=tc.get("classname", "") or "",
                name=tc.get("name", "") or "",
                outcome=outcome,
                message=message,
                details=details,
                req_ids=req_ids,
                file=tc.get("file", "") or "",
            )
        )
    return results


def load_junit(path: Path) -> list[TestResult]:
    return parse_junit_text(Path(path).read_bytes())


def parse_requirements_text(text: str) -> list[Requirement]:
    """Parse requirements CSV content. Raises ValueError if required columns are missing."""
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [f.strip() for f in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise ValueError(f"requirements CSV is missing columns: {', '.join(missing)}")
    reqs: list[Requirement] = []
    for row in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        if not row.get("req_id"):
            continue
        reqs.append(
            Requirement(
                req_id=row["req_id"],
                area=row["area"],
                requirement=row["requirement"],
                spec_path=row["spec_path"],
                verification=row["verification"],
            )
        )
    return reqs


def load_requirements(path: Path) -> list[Requirement]:
    return parse_requirements_text(Path(path).read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------- model

def requirement_status(req: Requirement, linked: list[TestResult]) -> str:
    if not linked:
        return STATUS_NOT_AUTOMATED if req.verification == "review" else STATUS_UNTESTED
    outcomes = {t.outcome for t in linked}
    if outcomes & {FAIL, ERROR}:
        return STATUS_FAIL
    if outcomes == {PASS}:
        return STATUS_PASS
    return STATUS_SKIP


def summarize(tests: list[TestResult]) -> dict:
    """Counts per category ('unit', 'requirement') and 'total'."""
    summary = {}
    for key in (CATEGORY_UNIT, CATEGORY_REQ, "total"):
        summary[key] = {o: 0 for o in OUTCOMES} | {"total": 0}
    for t in tests:
        for key in (t.category, "total"):
            summary[key][t.outcome] += 1
            summary[key]["total"] += 1
    return summary


def build_report(tests: list[TestResult], reqs: list[Requirement]) -> ReportModel:
    by_req: dict[str, list[TestResult]] = {}
    for t in tests:
        for rid in t.req_ids:
            by_req.setdefault(rid, []).append(t)

    known = {r.req_id for r in reqs}
    rows = [
        ReqRow(r, by_req.get(r.req_id, []), requirement_status(r, by_req.get(r.req_id, [])))
        for r in reqs
    ]
    unknown = {
        rid: [t.node_id for t in ts]
        for rid, ts in sorted(by_req.items())
        if rid not in known
    }
    return ReportModel(
        summary=summarize(tests),
        failures=[t for t in tests if t.outcome in (FAIL, ERROR)],
        rows=rows,
        orphans=[t for t in tests if not t.req_ids],
        unknown_req_ids=unknown,
    )


def _status_counts(model: ReportModel) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for row in model.rows:
        counts[row.status] += 1
    return counts


def _test_label(t: TestResult) -> str:
    return f"{t.node_id} ({t.outcome})"


# ---------------------------------------------------------------- Markdown

def _md_cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def render_markdown(model: ReportModel) -> str:
    out: list[str] = ["# Test report", ""]

    out += ["## 1. Summary", "", "| Category | Total | Pass | Fail | Error | Skip |", "|---|---:|---:|---:|---:|---:|"]
    for key, label in ((CATEGORY_UNIT, "Unit"), (CATEGORY_REQ, "Requirement"), ("total", "Total")):
        c = model.summary[key]
        out.append(f"| {label} | {c['total']} | {c['pass']} | {c['fail']} | {c['error']} | {c['skip']} |")
    counts = _status_counts(model)
    out += [
        "",
        f"Requirements ({len(model.rows)}): "
        + ", ".join(f"{s} {counts[s]}" for s in STATUSES),
        "",
    ]

    out += ["## 2. Failures", ""]
    if not model.failures:
        out += ["No failures or errors.", ""]
    for t in model.failures:
        out.append(f"### {t.node_id} ({t.outcome})")
        out.append("")
        if t.message:
            out += [f"Message: {t.message}", ""]
        if t.details:
            out += ["```text", t.details, "```", ""]

    out += ["## 3. Requirement traceability matrix", ""]
    if not model.rows:
        out += ["No requirements loaded.", ""]
    else:
        out += [
            "| Req ID | Area | Requirement | Verification | Tests | Status |",
            "|---|---|---|---|---|---|",
        ]
        for row in model.rows:
            r = row.requirement
            tests = "; ".join(_test_label(t) for t in row.tests) or "-"
            status = f"**{row.status}**" if row.status in (STATUS_UNTESTED, STATUS_FAIL) else row.status
            out.append(
                f"| {_md_cell(r.req_id)} | {_md_cell(r.area)} | {_md_cell(r.requirement)} | "
                f"{_md_cell(r.verification)} | {_md_cell(tests)} | {status} |"
            )
        out.append("")
    if model.unknown_req_ids:
        out += ["### Unknown requirement IDs referenced by tests", ""]
        for rid, nodes in model.unknown_req_ids.items():
            out.append(f"- {rid}: " + ", ".join(f"`{n}`" for n in nodes))
        out.append("")

    out += ["## 4. Orphan tests (no requirement property)", ""]
    if not model.orphans:
        out += ["None.", ""]
    for t in model.orphans:
        out.append(f"- `{t.node_id}` ({t.category}, {t.outcome})")
    if model.orphans:
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- HTML

_HTML_STYLE = """
body { font-family: system-ui, sans-serif; margin: 2rem; color: #1d1d1f; background: #fff; }
h1 { margin-top: 0; }
table { border-collapse: collapse; margin: 0.5rem 0 1.5rem; width: 100%; }
th, td { border: 1px solid #d0d0d7; padding: 0.35rem 0.5rem; text-align: left; vertical-align: top; font-size: 0.9rem; }
th { background: #f2f2f5; }
td.num { text-align: right; }
code, pre { font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem; }
pre { background: #f6f6f8; padding: 0.6rem; overflow-x: auto; white-space: pre-wrap; }
.status-PASS { color: #1a7f37; font-weight: 600; }
.status-FAIL, .status-UNTESTED { color: #b42318; font-weight: 700; }
.status-NOT-AUTOMATED { color: #475467; }
.status-SKIP { color: #9a6700; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e6e6; background: #151518; }
  th { background: #26262c; }
  th, td { border-color: #3a3a42; }
  pre { background: #1f1f25; }
}
"""


def _h(text: object) -> str:
    return html_lib.escape(str(text), quote=True)


def render_html(model: ReportModel) -> str:
    out: list[str] = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Test report</title>",
        f"<style>{_HTML_STYLE}</style>",
        "</head><body>",
        "<h1>Test report</h1>",
        "<h2>1. Summary</h2>",
        "<table><tr><th>Category</th><th>Total</th><th>Pass</th><th>Fail</th><th>Error</th><th>Skip</th></tr>",
    ]
    for key, label in ((CATEGORY_UNIT, "Unit"), (CATEGORY_REQ, "Requirement"), ("total", "Total")):
        c = model.summary[key]
        out.append(
            f"<tr><td>{label}</td>"
            + "".join(f'<td class="num">{c[k]}</td>' for k in ("total", "pass", "fail", "error", "skip"))
            + "</tr>"
        )
    out.append("</table>")
    counts = _status_counts(model)
    out.append(
        f"<p>Requirements ({len(model.rows)}): "
        + ", ".join(f'<span class="status-{s}">{s} {counts[s]}</span>' for s in STATUSES)
        + "</p>"
    )

    out.append("<h2>2. Failures</h2>")
    if not model.failures:
        out.append("<p>No failures or errors.</p>")
    for t in model.failures:
        out.append(f"<h3>{_h(t.node_id)} ({_h(t.outcome)})</h3>")
        if t.message:
            out.append(f"<p>Message: {_h(t.message)}</p>")
        if t.details:
            out.append(f"<pre>{_h(t.details)}</pre>")

    out.append("<h2>3. Requirement traceability matrix</h2>")
    if not model.rows:
        out.append("<p>No requirements loaded.</p>")
    else:
        out.append(
            "<table><tr><th>Req ID</th><th>Area</th><th>Requirement</th>"
            "<th>Verification</th><th>Tests</th><th>Status</th></tr>"
        )
        for row in model.rows:
            r = row.requirement
            tests = "<br>".join(f"<code>{_h(_test_label(t))}</code>" for t in row.tests) or "-"
            out.append(
                f"<tr><td>{_h(r.req_id)}</td><td>{_h(r.area)}</td><td>{_h(r.requirement)}</td>"
                f"<td>{_h(r.verification)}</td><td>{tests}</td>"
                f'<td class="status-{row.status}">{row.status}</td></tr>'
            )
        out.append("</table>")
    if model.unknown_req_ids:
        out.append("<h3>Unknown requirement IDs referenced by tests</h3><ul>")
        for rid, nodes in model.unknown_req_ids.items():
            out.append(f"<li>{_h(rid)}: " + ", ".join(f"<code>{_h(n)}</code>" for n in nodes) + "</li>")
        out.append("</ul>")

    out.append("<h2>4. Orphan tests (no requirement property)</h2>")
    if not model.orphans:
        out.append("<p>None.</p>")
    else:
        out.append("<ul>")
        for t in model.orphans:
            out.append(f"<li><code>{_h(t.node_id)}</code> ({_h(t.category)}, {_h(t.outcome)})</li>")
        out.append("</ul>")

    out.append("</body></html>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--junit", default=str(REPO_ROOT / "reports" / "junit.xml"))
    parser.add_argument("--requirements", default=str(REPO_ROOT / "docs" / "requirements.csv"))
    parser.add_argument("--out", default=str(REPO_ROOT / "reports" / "test_report.md"))
    parser.add_argument("--html", default=None, help="also write a single-file HTML report here")
    args = parser.parse_args(argv)

    junit_path = Path(args.junit)
    req_path = Path(args.requirements)
    if not junit_path.is_file():
        print(f"error: junit file not found: {junit_path}", file=sys.stderr)
        return 2
    if not req_path.is_file():
        print(f"error: requirements file not found: {req_path}", file=sys.stderr)
        return 2

    try:
        reqs = load_requirements(req_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    model = build_report(load_junit(junit_path), reqs)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(model), encoding="utf-8", newline="\n")
    print(f"wrote {out_path}")

    if args.html:
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html(model), encoding="utf-8", newline="\n")
        print(f"wrote {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
