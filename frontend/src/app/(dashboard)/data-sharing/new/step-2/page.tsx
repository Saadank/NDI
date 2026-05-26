import { Step2_DataSelection } from "@/components/features/data-sharing/NewRequest/Step2_DataSelection";
import { WizardStepIndicator } from "@/components/features/data-sharing/NewRequest/WizardStepIndicator";

export default function RaiseRequestStep2Page() {
  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <h1 className="text-lg font-bold text-auth-text">Raise New Request</h1>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto p-6 px-8">
        <div className="flex h-12 items-center">
          <WizardStepIndicator activeStep={2} />
        </div>
        <Step2_DataSelection />
      </div>
    </div>
  );
}
