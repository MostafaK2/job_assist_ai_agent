import Link from "next/link";

export default function Home() {
  return (
    <section className="py-10">
      <h1 className="text-4xl font-bold tracking-tight">Find jobs that fit you, and apply faster.</h1>
      <p className="mt-4 max-w-xl text-lg text-muted">
        Upload your resume, tell the agent what you&apos;re looking for, and review every application
        before it&apos;s filled in.
      </p>
      <div className="mt-8 flex gap-3">
        <Link href="/onboarding" className="rounded-md bg-ink px-5 py-3 font-medium text-white">
          Set up your profile
        </Link>
        <Link href="/chat" className="rounded-md border border-line bg-surface px-5 py-3 font-medium">
          Go to chat
        </Link>
      </div>
    </section>
  );
}
