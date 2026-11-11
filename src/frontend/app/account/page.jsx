import PageHeader from "@/components/PageHeader";

export const metadata = { title: "Your account" };

export default function AccountPage() {
  return (
    <div className="max-w-3xl">
      <PageHeader title="Your account" description="Your resume details, job preferences and employment information." />
      <p className="rounded-lg border border-dashed border-line bg-surface p-6 text-muted">Coming next.</p>
    </div>
  );
}
