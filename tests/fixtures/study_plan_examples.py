from feature_achievement.study_agent.plan_contracts import PlanItem, PlanStage, StudyPlan

MULTI_STAGE_SPRING_PLAN = StudyPlan(
    plan_id="plan-spring-boot-foundations",
    goal_summary="Learn Spring Boot foundations before moving into persistence.",
    stages=[
        PlanStage(
            stage_id="stage-1",
            title="Spring Foundations",
            order=1,
            items=[
                PlanItem(
                    item_id="item-ssh-ch1",
                    book_id="spring-start-here",
                    chapter_id="spring-start-here::ch1",
                    order=1,
                    why="Introduces the Spring ecosystem and application context.",
                ),
                PlanItem(
                    item_id="item-ssh-ch2",
                    book_id="spring-start-here",
                    chapter_id="spring-start-here::ch2",
                    order=2,
                    why="Builds core container understanding needed for later chapters.",
                    prerequisite_item_ids=["item-ssh-ch1"],
                ),
            ],
        ),
        PlanStage(
            stage_id="stage-2",
            title="Persistence Track",
            order=2,
            items=[
                PlanItem(
                    item_id="item-sia-ch3",
                    book_id="spring-in-action",
                    chapter_id="spring-in-action::ch3",
                    order=1,
                    why="Introduces concrete Spring data access patterns.",
                    prerequisite_item_ids=["item-ssh-ch1", "item-ssh-ch2"],
                ),
                PlanItem(
                    item_id="item-ssh-ch12",
                    book_id="spring-start-here",
                    chapter_id="spring-start-here::ch12",
                    order=2,
                    why="Reinforces data source usage with a more focused application angle.",
                    prerequisite_item_ids=["item-sia-ch3"],
                ),
            ],
        ),
    ],
    next_recommended_item_id="item-ssh-ch1",
)
