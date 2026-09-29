"""Shared pytest configuration.

No test is allowed to reach the network, so anything that would wait on a
remote service is neutralised here rather than in each individual test.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
