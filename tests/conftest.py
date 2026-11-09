"""Shared pytest configuration: copy requirement ids into the junit XML."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _record_req_ids(request, record_property):
    """One ``req`` junit property per requirement id in @pytest.mark.req(...)."""
    for marker in request.node.iter_markers("req"):
        for req_id in marker.args:
            record_property("req", req_id)
