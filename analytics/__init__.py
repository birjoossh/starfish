"""Analytics module — signal computation engines.

Each engine is stateless: DataFrame in, DataFrame out. Engines self-register
with :mod:`analytics.registry` at import time via the ``@register_engine``
decorator, so adding a new signal is a single-file change:

1. Drop ``analytics/<name>_engine.py`` exposing a decorated
   ``compute_<name>`` function.
2. Add the import to the auto-discovery block below.

The orchestrator (``analytics.compute_signals``) can then iterate
``registry.list_engines()`` to see every available signal — no edit
required to *know about* a new engine.
"""

# Import order is deliberate: each import triggers @register_engine on the
# module's compute function. Listed in dependency order so docs render
# sensibly.
from analytics import returns_engine  # noqa: F401  registers "returns"
from analytics import volume_engine  # noqa: F401  registers "volume"
from analytics import rs_engine  # noqa: F401  registers "rs"
from analytics import trend_stability_engine  # noqa: F401  registers "trend_stability"
