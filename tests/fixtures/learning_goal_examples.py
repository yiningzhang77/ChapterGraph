from feature_achievement.study_agent.goal_contracts import GoalConstraints, LearningGoal

BEGINNER_SPRING_BOOT_GOAL = LearningGoal(
    goal_type="learn_topic",
    primary_topics=["Spring Boot", "Spring fundamentals"],
    background_topics=["Java basics"],
    desired_depth="practical",
    constraints=GoalConstraints(
        exclude_topics=["reactive"],
    ),
    goal_summary="Learn Spring Boot from scratch with a practical backend focus.",
)

SPRING_PERSISTENCE_GOAL = LearningGoal(
    goal_type="build_roadmap",
    primary_topics=["data persistence", "Spring Data JPA", "JdbcTemplate"],
    background_topics=["Java", "Spring basics"],
    desired_depth="deep",
    constraints=GoalConstraints(
        time_budget_hours=20,
        preferred_books=["spring-start-here", "spring-in-action"],
    ),
    goal_summary="Build a focused Spring persistence learning roadmap.",
)
