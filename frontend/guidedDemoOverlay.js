export function renderGuidedDemoOverlay(h, {
    active,
    stepDetails,
    stepIndex,
    totalSteps,
    isRunning,
    readyForNext,
    phase,
    error,
    onNext,
    onStop,
    onRestart,
}) {
    if (!active) {
        return null;
    }

    let phaseLabel = "准备中";
    if (error) {
        phaseLabel = "演示出错";
    } else if (phase === "finished") {
        phaseLabel = "演示完成";
    } else if (isRunning) {
        phaseLabel = "系统正在执行当前步骤";
    } else if (readyForNext) {
        phaseLabel = "当前步骤已完成，可进入下一步";
    }

    const isFinished = phase === "finished";

    return h(
        "div",
        {
            className: error
                ? "guidedDemoOverlay guidedDemoOverlayError"
                : "guidedDemoOverlay",
        },
        h("div", { className: "guidedDemoOverlayBadge" }, `步骤 ${stepIndex + 1} / ${totalSteps}`),
        h("div", { className: "guidedDemoOverlayTitle" }, stepDetails?.title ?? "回放演示"),
        h("div", { className: "guidedDemoOverlayPhase" }, phaseLabel),
        error
            ? h("div", { className: "guidedDemoOverlayText" }, error)
            : h("div", { className: "guidedDemoOverlayText" }, stepDetails?.text ?? ""),
        !error && stepDetails?.actionText
            ? h("div", { className: "guidedDemoOverlayAction" }, stepDetails.actionText)
            : null,
        h(
            "div",
            { className: "guidedDemoOverlayActions" },
            h(
                "button",
                {
                    type: "button",
                    className: "guidedDemoOverlayBtn secondary",
                    onClick: onStop,
                },
                "退出演示",
            ),
            error || isFinished
                ? h(
                    "button",
                    {
                        type: "button",
                        className: "guidedDemoOverlayBtn primary",
                        onClick: onRestart,
                    },
                    "重新回放",
                )
                : h(
                    "button",
                    {
                        type: "button",
                        className: "guidedDemoOverlayBtn primary",
                        onClick: onNext,
                        disabled: isRunning || !readyForNext,
                    },
                    isRunning ? "执行中..." : "下一步",
                ),
        ),
    );
}
