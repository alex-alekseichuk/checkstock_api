"""End-to-end tests: full app (routes -> services -> repos) against a real
Postgres database with a fresh schema per session.

These tests need a running Postgres reachable at ``CHECKSTOCK_E2E_DATABASE_URL``
(default: ``postgresql://checkstock:checkstock@localhost:5432/checkstock_e2e``,
i.e. the compose ``db`` service). If the database is not reachable, the whole
suite is skipped with an explanatory message instead of failing.
"""
