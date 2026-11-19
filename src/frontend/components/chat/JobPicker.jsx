"use client";

import { useState } from "react";
import { useAssistantTransportSendCommand, useAuiState } from "@assistant-ui/react";

/**
 * Gate 1: the search_jobs result as cards. Every job starts approved; Skip un-approves it,
 * Approve re-approves it. "Continue" sends {type: "job-decisions", toolCallId, skipped}
 * and the backend turns that into one message for the agent (it checks the ids itself).
 * Once a decision exists for this search, the card is read-only.
 */
export default function JobPicker({ toolCallId, artifact }) {
  const rows = artifact?.rows;
  const sendCommand = useAssistantTransportSendCommand();
  const isRunning = useAuiState((s) => s.thread.isRunning);
  // The saved decision for this search, if any (survives reloading the chat).
  const decision = useAuiState((s) =>
    s.thread.messages.find((m) => m.metadata?.custom?.jobDecisions?.toolCallId === toolCallId)
  )?.metadata.custom.jobDecisions;
  const [skipped, setSkipped] = useState(() => new Set());
  const [sent, setSent] = useState(false);

  if (!artifact) return <p className="animate-pulse text-sm text-muted motion-reduce:animate-none">Searching jobs…</p>;
  if (!rows?.length) return null; // the agent explains "no matches" in its reply

  const locked = Boolean(decision) || sent;
  const isSkipped = (id) => (decision ? decision.skipped.includes(id) : skipped.has(id));
  const approvedCount = rows.filter((r) => !isSkipped(r.id)).length;

  const toggle = (id, skip) =>
    setSkipped((prev) => {
      const next = new Set(prev);
      skip ? next.add(id) : next.delete(id);
      return next;
    });

  const send = () => {
    setSent(true);
    sendCommand({ type: "job-decisions", toolCallId, skipped: [...skipped] });
  };

  return (
    <section aria-label="Search results" className="my-3 overflow-hidden rounded-2xl border border-line bg-surface">
      <header className="flex items-center justify-between px-4 py-2.5 text-sm">
        <span className="font-semibold">{rows.length} of {artifact.total} matches, best first</span>
        {artifact.hidden_applied > 0 && <span className="text-muted">{artifact.hidden_applied} already applied, hidden</span>}
      </header>

      <ul>
        {rows.map((job) => (
          <JobCard key={job.id} job={job} skipped={isSkipped(job.id)} locked={locked} onToggle={toggle} />
        ))}
      </ul>

      <footer className="flex items-center justify-between gap-3 border-t border-line bg-paper px-4 py-3 text-sm">
        <span className="text-muted">
          {approvedCount} approved · {rows.length - approvedCount} skipped
        </span>
        {locked ? (
          <span className="font-medium text-go">{approvedCount ? "Sent, preparing applications" : "Sent"}</span>
        ) : (
          <button
            type="button"
            onClick={send}
            disabled={isRunning}
            className="rounded-full bg-go px-4 py-1.5 font-medium text-white disabled:opacity-40"
          >
            {approvedCount ? `Continue with ${approvedCount} job${approvedCount === 1 ? "" : "s"}` : "Continue without these"}
          </button>
        )}
      </footer>
    </section>
  );
}

function JobCard({ job, skipped, locked, onToggle }) {
  return (
    <li className={`grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-t border-line px-4 py-3 ${skipped ? "" : "bg-go/10"}`}>
      <div className={`min-w-0 ${skipped ? "text-muted" : ""}`}>
        <div className="flex flex-wrap items-center gap-2">
          <a href={job.url} target="_blank" rel="noopener noreferrer" className="font-semibold hover:underline">
            {job.title}
          </a>
          <span className="rounded-md bg-ink/5 px-2 py-0.5 text-xs font-semibold">{job.score}</span>
        </div>
        <p className="mt-0.5 text-sm text-muted">
          {[job.company, job.location, job.work_types?.join("/"), job.posted && `posted ${job.posted}`].filter(Boolean).join(" · ")}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
          {job.reasons?.map((r) => (
            <span key={r} className="rounded-md bg-paper px-2 py-0.5 text-muted">{r}</span>
          ))}
          {job.warnings?.map((w) => (
            <span key={w} className="rounded-md bg-highlight/25 px-2 py-0.5 text-ink">⚠ {w}</span>
          ))}
        </div>
      </div>

      {locked ? (
        <span className={`self-start text-sm font-medium ${skipped ? "text-muted" : "text-go"}`}>
          {skipped ? "Skipped" : "✓ Approved"}
        </span>
      ) : (
        <div role="group" aria-label={`Decision for ${job.title}`} className="flex self-start overflow-hidden rounded-full border border-line text-sm">
          <button
            type="button"
            aria-pressed={!skipped}
            onClick={() => onToggle(job.id, false)}
            className={`px-3 py-1 ${skipped ? "hover:bg-paper" : "bg-go text-white"}`}
          >
            ✓ Approve
          </button>
          <button
            type="button"
            aria-pressed={skipped}
            onClick={() => onToggle(job.id, true)}
            className={`border-l border-line px-3 py-1 ${skipped ? "bg-ink text-white" : "hover:bg-paper"}`}
          >
            Skip
          </button>
        </div>
      )}
    </li>
  );
}