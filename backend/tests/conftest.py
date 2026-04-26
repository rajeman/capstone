"""Pytest bootstrap: Settings() loads at import time — minimal env before app imports."""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URI", "mongodb://127.0.0.1:27017/capstone_pytest")
os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_pytest_dummy_secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-pytest-dummy")
