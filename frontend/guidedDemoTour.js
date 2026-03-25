import Shepherd from "https://esm.sh/shepherd.js@13.0.0?bundle";
import { GUIDED_DEMO_STEP_DETAILS } from "./guidedDemo.js";

const STEP_TARGETS = {
    intro: "#guidedDemoTrigger",
    expand_books: "#graph",
    term_mode: "[data-demo-role='ask-mode-term']",
    actuator_question: "#guidedDemoTermInput",
    actuator_result: "#guidedDemoMessages",
    broad_question: "#guidedDemoQueryInput",
    blocked_result: "[data-demo-role='suggestions']",
    narrowed_question: "#guidedDemoTermInput",
    finished: "#guidedDemoTrigger",
};

function resolveAttachTarget(stepId) {
    const selector = STEP_TARGETS[stepId] ?? "#askPanel";
    if (typeof document !== "undefined" && document.querySelector(selector)) {
        return selector;
    }
    return "#askPanel";
}

export function createGuidedDemoTour({ onCancel } = {}) {
    const tour = new Shepherd.Tour({
        useModalOverlay: true,
        defaultStepOptions: {
            cancelIcon: { enabled: true },
            scrollTo: { behavior: "smooth", block: "center" },
            classes: "chaptergraph-guided-demo-tour",
        },
    });

    Object.entries(GUIDED_DEMO_STEP_DETAILS).forEach(([stepId, details]) => {
        tour.addStep({
            id: stepId,
            title: details.title,
            text: details.text,
            attachTo: {
                element: resolveAttachTarget(stepId),
                on: "left",
            },
            buttons: [
                {
                    text: stepId === "finished" ? "Done" : "Stop",
                    action: () => tour.cancel(),
                },
            ],
        });
    });

    if (typeof onCancel === "function") {
        tour.on("cancel", onCancel);
    }

    return {
        start(stepId = "intro") {
            if (tour.steps.length === 0) return;
            tour.start();
            this.show(stepId);
        },
        show(stepId) {
            const nextStep = tour.getById(stepId);
            if (!nextStep) return;
            nextStep.options.attachTo = {
                element: resolveAttachTarget(stepId),
                on: "left",
            };
            tour.show(stepId);
        },
        cancel() {
            tour.cancel();
        },
    };
}
