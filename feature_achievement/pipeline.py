import warnings

warnings.warn(
    "feature_achievement.pipeline is deprecated; use feature_achievement.retrieval.*",
    DeprecationWarning,
    stacklevel=2,
)

from feature_achievement.legacy.pipeline import *  # noqa: F401,F403

