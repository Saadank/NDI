import { Step3_Review } from "@/components/features/data-sharing/NewRequest/Step3_Review";
import { WizardStepIndicator } from "@/components/features/data-sharing/NewRequest/WizardStepIndicator";

export default function RaiseRequestStep3Page() {
  return (
    <div className="relative flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <h1 className="text-lg font-bold text-auth-text">Raise New Request</h1>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto px-8 py-6">
        <div className="flex h-12 items-center">
          <WizardStepIndicator activeStep={3} />
        </div>
        <Step3_Review />
      </div>
    </div>
  );
}
