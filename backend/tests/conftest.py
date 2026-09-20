"""Shared pytest configuration.

No test is allowed to reach the network, so anything that would wait on a
remote service is neutralised here rather than in each individual test.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(autouse=True)
def no_network_backoff(monkeypatch):
    """Zero the Overpass retry backoff for the whole suite.

    The loader deliberately sleeps between retries against real public
    endpoints, but tests inject their own transport, so the sleep is pure
    dead time - it added ~19 s to the suite before this was added.
    """
    import realdata.osm_loader as osm_loader

    monkeypatch.setattr(osm_loader, "RETRY_BACKOFF_S", 0.0)
