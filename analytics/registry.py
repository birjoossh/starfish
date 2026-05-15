"""Signal-engine registry — composable analytics contract.

Each analytics engine in this package is a pure DataFrame-in, DataFrame-out
function. Engines self-register here at import time via :func:`register_engine`
so the orchestrator can list, look up, and dispatch them by name rather than
by hard-coded imports.

Spec ref: Section 13.3 Key Decision 1 — "analytics is entirely stateless and
pure Python; each engine takes a DataFrame in, returns a DataFrame out".

The registry holds metadata, not state. To add a new signal:

1. Write ``analytics/<name>_engine.py`` exposing ``def compute_<name>(...)``.
2. Decorate it::

       @register_engine(
           name="<name>",
           inputs=("prices",),
           outputs=("trade_date", "symbol", "<col>", ...),
       )
       def compute_<name>(prices_df):
           ...

3. Import it in ``analytics/__init__.py`` so the decorator fires.

That's it — no orchestrator edit required to *know about* the engine. The
orchestrator can iterate :func:`list_engines` and resolve inputs from a
single ``frames`` dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import pandas as pd


@dataclass(frozen=True)
class EngineSpec:
    """Static description of a registered analytics engine."""

    name: str
    fn: Callable[..., pd.DataFrame]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]


_REGISTRY: dict[str, EngineSpec] = {}


def register_engine(
    *,
    name: str,
    inputs: Iterable[str],
    outputs: Iterable[str],
) -> Callable[[Callable[..., pd.DataFrame]], Callable[..., pd.DataFrame]]:
    """Decorator: register a DataFrame-in / DataFrame-out engine.

    Args:
        name: Unique short identifier (e.g. ``"returns"``).
        inputs: Names of DataFrames the engine consumes, in positional
            order. Resolved against the ``frames`` dict passed to
            :func:`run_engine` / :func:`run_all`.
        outputs: Column names the resulting DataFrame is expected to
            carry. Used for documentation + sanity checks.

    Raises:
        ValueError: if ``name`` is already registered.
    """

    inputs_t = tuple(inputs)
    outputs_t = tuple(outputs)

    def decorator(fn: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
        if name in _REGISTRY:
            raise ValueError(
                f"Engine '{name}' is already registered "
                f"(by {_REGISTRY[name].fn.__module__}.{_REGISTRY[name].fn.__qualname__})."
            )
        _REGISTRY[name] = EngineSpec(
            name=name, fn=fn, inputs=inputs_t, outputs=outputs_t
        )
        return fn

    return decorator


def list_engines() -> list[EngineSpec]:
    """Return all registered engines in registration order."""
    return list(_REGISTRY.values())


def get_engine_spec(name: str) -> EngineSpec:
    """Look up an engine by name."""
    return _REGISTRY[name]


def run_engine(name: str, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Dispatch a single engine by name.

    Args:
        name: Registered engine name.
        frames: Available DataFrames keyed by the names referenced in
            ``EngineSpec.inputs``.

    Returns:
        The engine's output DataFrame.

    Raises:
        KeyError: if ``name`` is not registered or a required input is
            absent from ``frames``.
    """
    spec = _REGISTRY[name]
    args = [frames[key] for key in spec.inputs]
    return spec.fn(*args)


def run_all(
    frames: dict[str, pd.DataFrame],
    *,
    only: Iterable[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Run every registered engine that has its inputs available.

    Engines whose inputs are missing from ``frames`` are silently skipped —
    callers can detect this by comparing the result keys with the engine list.

    Args:
        frames: Available named DataFrames.
        only: Optional allow-list of engine names; runs the full registry
            if not provided.

    Returns:
        Dict mapping engine name → output DataFrame.
    """
    allowed = set(only) if only is not None else None
    out: dict[str, pd.DataFrame] = {}
    for spec in list_engines():
        if allowed is not None and spec.name not in allowed:
            continue
        if not all(key in frames for key in spec.inputs):
            continue
        out[spec.name] = spec.fn(*(frames[key] for key in spec.inputs))
    return out


def _clear_registry_for_tests() -> None:
    """Test-only: reset the registry. Do not call from production code."""
    _REGISTRY.clear()
