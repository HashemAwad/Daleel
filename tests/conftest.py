"""Shared test setup.

Turn recording is off for the whole suite, so tests that call pipeline.handle don't write
metadata rows into the dev database. tests/test_data_retention.py switches it back on."""
import os

os.environ["RECORD_TURNS"] = "0"
