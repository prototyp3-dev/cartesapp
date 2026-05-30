"""Shared fixtures for the cartesapp framework unit suite.

These tests exercise the in-machine ``run`` flow internals (decode strategies,
request lifecycle, registration, output normalization) as pure Python — no
Docker, no cartesi-machine, and without binding the global Pony database.

The framework keeps all registration state on class-level singletons that are
populated as import side effects, so state leaks between successive
``setup_manager``/registration calls. ``Manager.reset()`` is invoked before
every test to guarantee isolation.
"""
import pytest

from cartesapp.manager import Manager


@pytest.fixture(autouse=True)
def reset_framework_state():
    Manager.reset()
    yield
    Manager.reset()
