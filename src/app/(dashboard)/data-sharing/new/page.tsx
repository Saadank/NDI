import { Step1_BasicInfo } from "@/components/features/data-sharing/NewRequest/Step1_BasicInfo";
import { WizardStepIndicator } from "@/components/features/data-sharing/NewRequest/WizardStepIndicator";

export default function NewDataSharingRequestPage() {
  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center justify-between px-8"
        style={{
          backgroundColor: "#FFFFFF",
          borderBottom: "1px solid #EEEEEE",
        }}
      >
        <h1 className="text-lg font-bold text-auth-text">Raise New Request</h1>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-auto p-6 px-8">
        <div className="flex h-12 items-center">
          <WizardStepIndicator activeStep={1} />
        </div>

        <div
          className="flex flex-col gap-4 rounded-lg p-6"
          style={{
            backgroundColor: "#FFFFFF",
            border: "1px solid #EEEEEE",
          }}
        >
          <Step1_BasicInfo />
        </div>
      </div>
    </div>
  );
}
