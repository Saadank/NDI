"use client";

const STEPS = [
  { n: 1, label: "Details" },
  { n: 2, label: "Data Source" },
  { n: 3, label: "Review & Submit" },
] as const;

export function WizardStepIndicator({
  activeStep,
}: {
  activeStep: 1 | 2 | 3;
}) {
  return (
    <div className="flex w-full items-center">
      {STEPS.map((step, i) => {
        const isActive = step.n === activeStep;
        const isDone = step.n < activeStep;
        return (
          <div key={step.n} className="flex flex-1 items-center">
            <div className="flex items-center gap-2">
              <span
                className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold"
                style={{
                  backgroundColor:
                    isActive || isDone ? "#D76736" : "#EEEEEE",
                  color: isActive || isDone ? "#FFFFFF" : "#9E9E9E",
                }}
              >
                {step.n}
              </span>
              <span
                className="text-[13px]"
                style={{
                  color: isActive ? "#D76736" : isDone ? "#070709" : "#9E9E9E",
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span
                className="mx-3 h-0.5 flex-1"
                style={{
                  backgroundColor: step.n < activeStep ? "#D76736" : "#EEEEEE",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
