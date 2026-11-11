import PageHeader from "@/components/PageHeader";
import OnboardingFlow from "@/components/onboarding/OnboardingFlow";

export const metadata = { title: "Set up your profile" };

export default function OnboardingPage() {
  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Set up your profile"
        description="Upload your resume, check what we found, and tell us the jobs you want."
      />
      <OnboardingFlow />
    </div>
  );
}