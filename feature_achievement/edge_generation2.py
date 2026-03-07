import warnings

warnings.warn(
    "feature_achievement.edge_generation2 is deprecated; use feature_achievement.retrieval.*",
    DeprecationWarning,
    stacklevel=2,
)

from feature_achievement.legacy.edge_generation2 import *  # noqa: F401,F403

