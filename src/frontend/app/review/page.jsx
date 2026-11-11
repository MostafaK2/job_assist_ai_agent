import PageHeader from "@/components/PageHeader";

export const metadata = { title: "Review" };

export default function ReviewPage() {
  return (
    <>
      <PageHeader title="Review" description="Check the drafted answers before the agent fills in each application." />
      <p className="rounded-lg border border-dashed border-line bg-surface p-6 text-muted">Coming next.</p>
    </>
  );
}
