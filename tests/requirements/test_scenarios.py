"""Scenario-fixture driven requirement tests (tests/fixtures/<name>/)."""

import pytest

from .helpers import run_error_scenario, run_scenario

R = pytest.mark.req

RUN = [
    ("minimal", ("REQ-029", "REQ-083", "REQ-085", "REQ-089")),
    ("ap_engage", ("REQ-023", "REQ-024", "REQ-036", "REQ-038", "REQ-089", "REQ-090", "REQ-109")),
    ("multirate", ("REQ-041", "REQ-042", "REQ-043", "REQ-044", "REQ-057", "REQ-058")),
    ("conflict", ("REQ-028", "REQ-056")),
    ("global_transition", ("REQ-026", "REQ-027")),
    ("and_rows", ("REQ-021", "REQ-022")),
    ("reuse_equation", ("REQ-014", "REQ-015", "REQ-016", "REQ-091")),
    ("order_visibility", ("REQ-049", "REQ-050", "REQ-051", "REQ-052")),
]

ERRORS = [
    ("bad_syntax", ("REQ-065",)),
    ("bad_no_default", ("REQ-068",)),
    ("bad_dup_default", ("REQ-069",)),
    ("bad_mixed_band", ("REQ-070",)),
    ("bad_unknown_state", ("REQ-067",)),
    ("bad_dup_result_var", ()),
    ("bad_nonpositive_band", ("REQ-077",)),
    ("bad_inconsistent_transition_id", ("REQ-066", "REQ-071")),
]


@pytest.mark.parametrize(
    "name", [pytest.param(n, marks=R(*ids), id=n) for n, ids in RUN]
)
def test_run_scenario(name):
    run_scenario(name)


@pytest.mark.parametrize(
    "name", [pytest.param(n, marks=R(*ids) if ids else (), id=n) for n, ids in ERRORS]
)
def test_error_scenario(name):
    run_error_scenario(name)
