"""Unit tests for analytics.registry."""

from __future__ import annotations

import pandas as pd
import pytest

from analytics import registry


@pytest.fixture(autouse=True)
def fresh_registry():
    """Snapshot the live registry and restore after each test."""
    saved = dict(registry._REGISTRY)
    registry._clear_registry_for_tests()
    yield
    registry._clear_registry_for_tests()
    registry._REGISTRY.update(saved)


def _df(**cols):
    return pd.DataFrame(cols)


def test_register_and_list():
    @registry.register_engine(name="alpha", inputs=("x",), outputs=("a",))
    def fn(x):
        return x

    engines = registry.list_engines()
    assert [e.name for e in engines] == ["alpha"]
    assert engines[0].inputs == ("x",)
    assert engines[0].outputs == ("a",)


def test_duplicate_registration_raises():
    @registry.register_engine(name="dup", inputs=("x",), outputs=("a",))
    def fn1(x):
        return x

    with pytest.raises(ValueError, match="already registered"):
        @registry.register_engine(name="dup", inputs=("x",), outputs=("a",))
        def fn2(x):
            return x


def test_run_engine_dispatches_by_name():
    @registry.register_engine(name="add", inputs=("a", "b"), outputs=("sum",))
    def add(a, b):
        return pd.DataFrame({"sum": a["x"].values + b["y"].values})

    frames = {"a": _df(x=[1, 2, 3]), "b": _df(y=[10, 20, 30])}
    out = registry.run_engine("add", frames)
    assert out["sum"].tolist() == [11, 22, 33]


def test_run_engine_missing_input_raises_keyerror():
    @registry.register_engine(name="needs_x", inputs=("x",), outputs=("y",))
    def fn(x):
        return x

    with pytest.raises(KeyError):
        registry.run_engine("needs_x", {})


def test_run_all_skips_engines_with_missing_inputs():
    @registry.register_engine(name="ready", inputs=("p",), outputs=("v",))
    def ready(p):
        return _df(v=p["x"].values * 2)

    @registry.register_engine(name="blocked", inputs=("p", "missing"), outputs=("w",))
    def blocked(p, missing):
        return _df(w=[0])

    out = registry.run_all({"p": _df(x=[1, 2, 3])})
    assert set(out.keys()) == {"ready"}
    assert out["ready"]["v"].tolist() == [2, 4, 6]


def test_run_all_honours_only_filter():
    @registry.register_engine(name="a", inputs=("p",), outputs=("v",))
    def a(p):
        return _df(v=[1])

    @registry.register_engine(name="b", inputs=("p",), outputs=("v",))
    def b(p):
        return _df(v=[2])

    out = registry.run_all({"p": _df(x=[1])}, only={"b"})
    assert set(out.keys()) == {"b"}


def test_live_registry_has_expected_engines():
    """Importing analytics should auto-register the canonical engines.

    Re-running the @register_engine decorator means clearing and re-
    importing the engine modules themselves, not just the package init.
    """
    import importlib
    import sys

    registry._clear_registry_for_tests()
    for mod in (
        "analytics.returns_engine",
        "analytics.volume_engine",
        "analytics.rs_engine",
        "analytics.trend_stability_engine",
    ):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
        else:
            importlib.import_module(mod)

    names = {e.name for e in registry.list_engines()}
    assert {"returns", "volume", "rs", "trend_stability"}.issubset(names)
