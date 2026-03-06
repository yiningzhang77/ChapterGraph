from feature_achievement.db.engine import init_db
import feature_achievement.db.models  # noqa:F401
from feature_achievement.scripts.migrate_run_min_score import (
    migrate_run_min_store_to_min_score,
)

if __name__ == "__main__":
    init_db()
    migrate_run_min_store_to_min_score()
    print("DB initialized successfully")
