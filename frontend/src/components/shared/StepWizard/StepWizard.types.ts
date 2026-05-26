export interface WizardStep {
  id: string;
  title: string;
  description?: string;
}

export interface StepWizardProps {
  steps: WizardStep[];
  currentStep: number;
  onStepChange?: (step: number) => void;
  children?: React.ReactNode;
}
