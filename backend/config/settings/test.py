"""Test settings. Uses the same PostgreSQL server (pytest-django creates test_<db>)."""
import tempfile

from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only; tests never use real passwords
MEDIA_ROOT = tempfile.mkdtemp(prefix="electava-test-media-")
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"auth": "5/min"}  # noqa: F405
