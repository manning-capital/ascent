"""
Conftest for tests that don't use Prefect.

This conftest intentionally does NOT set up the Prefect test harness,
allowing tests in this directory to use postgres_test_harness with use_prefect=False
without conflicts.
"""

# No fixtures needed - tests will use postgres_test_harness directly with use_prefect=False
