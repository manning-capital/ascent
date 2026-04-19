"""Scenario-test fixtures: minimum DB seeding for end-to-end flows.

Re-exports :func:`seeded_ids` from the contract conftest so scenario tests
can seed a portfolio/strategy/exchange/instruments the router needs to
create trades. Kept separate from the contract conftest to avoid pytest's
plugin-registration collision when both conftest modules are discovered
via different paths.
"""

from __future__ import annotations

from tests.integration.contract.conftest import (  # noqa: F401
    SeededIds,
    seeded_ids,
)
