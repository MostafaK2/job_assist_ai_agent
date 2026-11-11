import PageHeader from "@/components/PageHeader";

export const metadata = { title: "Jobs" };

export default function JobsPage() {
  return (
    <>
      <PageHeader title="Jobs" description="Jobs that match your profile. Pick the ones you want to apply to." />
      <p className="rounded-lg border border-dashed border-line bg-surface p-6 text-muted">Coming next.</p>
    </>
  );
}
