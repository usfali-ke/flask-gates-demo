"""Shared fixtures for the suites that run against a deployed environment.

The app has no accounts and no database — notes live in the gunicorn
worker's memory — so there is no test user to create: unlike
django-gates-demo's suites, these run anonymously, and nothing here
depends on one job's notes not being visible to another (the dev and
staging controls run in parallel against the same pod).
"""

import pytest

from .client import BASE


@pytest.fixture(scope="session")
def base_url():
    return BASE
