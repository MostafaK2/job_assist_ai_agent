"use client";

import { useState } from "react";
import { useAssistantTransportSendCommand, useAssistantTransportState, useAuiState } from "@assistant-ui/react";

/**
 * Gate 2: the save_models_answers result as a review card.
 * The artifact (built on the server, private values masked) has one row per question, each in a
 * section: needs_you, assistant, auto (filled automatically), profile.
 * Buttons send {type: "review-decision", toolCallId, decision, edits, note}; the backend checks
 * the edits itself and tells the agent what to do next. Once decided, the card is read-only.
 */
const SECTIONS = [
  { key: "needs_you", title: "Needs you", hint: "Required, and only you can answer these." },
  { key: "assistant", title: "Written by the assistant", hint: "Check these. You can change them." },
  { key: "auto", title: "Filled automatically", hint: "Acknowledgements and similar answers." },
];

export default function ReviewCard({ toolCallId, artifact, result }) {
  if (!artifact) {
    // Still running: show progress. Finished without a card (an error, e.g. an expired
    // application): show nothing; the agent explains it in its reply.
    return result === undefined
      ? <p className="animate-pulse text-sm text-muted motion-reduce:animate-none">Saving answers…</p>
      : null;
  }
  // Keyed by draft so the editable answers start from this draft's values.
  return <ReviewBody key={artifact.draft_id} toolCallId={toolCallId} artifact={artifact} />;
}

function ReviewBody({ toolCallId, artifact }) {
  const sendCommand = useAssistantTransportSendCommand();
  const isRunning = useAuiState((s) => s.thread.isRunning);
  // The saved decision for this card, if any (survives reloading the chat).
  const decision = useAuiState((s) =>
    s.thread.messages.find((m) => m.metadata?.custom?.reviewDecision?.toolCallId === toolCallId)
  )?.metadata.custom.reviewDecision;
  // Only the newest card can be decided: older ones were replaced by a fix or a change request.
  const isLatest = useAuiState((s) => {
    const calls = s.thread.messages.flatMap((m) =>
      (m.content ?? []).filter((p) => p.type === "tool-call" && p.toolName === "save_models_answers")
    );
    return calls.at(-1)?.toolCallId === toolCallId;
  });

  const rows = artifact.rows ?? [];
  const [edits, setEdits] = useState(() =>
    Object.fromEntries(rows.filter((r) => r.editable).map((r) => [r.name, r.value ?? ""]))
  );
  const [mode, setMode] = useState(null); // null | "changes"
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(null); // {kind, at} until the server's saved decision shows up
  // The request failed (see recordFailedCommands): unlock and say why, instead of claiming "sent".
  const failure = useAssistantTransportState((s) =>
    s?.failedCommands?.findLast((f) => f.toolCallId === toolCallId)
  );
  const failed = Boolean(sent && !decision && failure && failure.at >= sent.at);

  const done = decision?.decision ?? (failed ? null : sent?.kind);
  const locked = Boolean(done) || !isLatest;
  const bySection = (key) => rows.filter((r) => r.section === key);
  const needsYou = bySection("needs_you");
  const profile = bySection("profile");

  const setEdit = (name, value) => {
    setError("");
    setEdits((prev) => ({ ...prev, [name]: value }));
  };

  const send = (kind) => {
    if (kind === "approve") {
      const empty = needsYou.filter((r) => r.editable && !String(edits[r.name] ?? "").trim());
      if (empty.length) return setError(`Fill in ${empty.map((r) => `"${short(r.label)}"`).join(", ")} first.`);
    }
    if (kind === "changes" && !note.trim()) return setError("Say what to change first.");
    setError("");
    setSent({ kind, at: Date.now() });
    sendCommand({
      type: "review-decision",
      toolCallId,
      decision: kind,
      ...(kind === "approve" && { edits: Object.fromEntries(Object.entries(edits).filter(([, v]) => String(v).trim())) }),
      ...(kind === "changes" && { note: note.trim() }),
    });
  };

  return (
    <section aria-label="Review application" className="my-3 overflow-hidden rounded-2xl border border-line bg-surface">
      <header className="flex items-start justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <a href={artifact.job.url} target="_blank" rel="noopener noreferrer" className="font-semibold hover:underline">
            {artifact.job.title}
          </a>
          <p className="text-sm text-muted">{artifact.job.id}</p>
        </div>
        <StatusPill done={done} stale={!isLatest && !done} needsYou={needsYou.length} />
      </header>

      <dl className="grid grid-cols-3 gap-2 px-4 pb-3 text-sm">
        <Count label="From your profile" value={profile.length + bySection("auto").length} />
        <Count label="By the assistant" value={bySection("assistant").length} />
        <Count label="Needs you" value={needsYou.length} warn={needsYou.length > 0} />
      </dl>

      {SECTIONS.map(({ key, title, hint }) => {
        const list = bySection(key);
        if (!list.length) return null;
        return (
          <div key={key} className="border-t border-line px-4 py-3">
            <h3 className={`text-sm font-semibold ${key === "needs_you" ? "text-stop" : ""}`}>{title}</h3>
            <p className="mb-2 text-xs text-muted">{hint}</p>
            <ul className="flex flex-col gap-3">
              {list.map((row) => (
                <Row key={row.name} row={row} value={edits[row.name]} locked={locked} onChange={setEdit} />
              ))}
            </ul>
          </div>
        );
      })}

      {profile.length > 0 && (
        <details className="border-t border-line px-4 py-3 text-sm">
          <summary className="cursor-pointer font-semibold">From your profile · {profile.length} answers</summary>
          <dl className="mt-2 flex flex-col gap-1.5">
            {profile.map((row) => (
              <div key={row.name} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3">
                <dt className="truncate text-muted" title={row.label}>{row.label}</dt>
                <dd className="truncate text-right"><Value row={row} /></dd>
              </div>
            ))}
          </dl>
        </details>
      )}

      <footer className="flex flex-col gap-2 border-t border-line bg-paper px-4 py-3 text-sm">
        {locked ? (
          <LockedNote done={done} decision={decision} />
        ) : mode === "changes" ? (
          <>
            <label htmlFor={`note-${toolCallId}`} className="font-medium">What should change?</label>
            <textarea
              id={`note-${toolCallId}`}
              rows={2}
              maxLength={2000}
              value={note}
              onChange={(e) => { setError(""); setNote(e.target.value); }}
              placeholder="Make the cover letter shorter and mention my Airflow work"
              className="rounded-lg border border-line bg-surface px-3 py-2"
            />
            <div className="flex gap-2">
              <Button primary onClick={() => send("changes")} disabled={isRunning}>Send changes</Button>
              <Button onClick={() => { setMode(null); setError(""); }}>Cancel</Button>
            </div>
          </>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Button primary onClick={() => send("approve")} disabled={isRunning}>Approve</Button>
            <Button onClick={() => setMode("changes")} disabled={isRunning}>Ask for changes</Button>
            <Button onClick={() => send("skip")} disabled={isRunning}>Skip this job</Button>
            <span className="text-xs text-muted">Nothing is submitted. Your edits are saved when you approve.</span>
          </div>
        )}
        {(error || failed) && (
          <p role="alert" className="text-xs text-stop">
            {error || `That didn't go through. ${errorText(failure.message)}`}
          </p>
        )}
      </footer>
    </section>
  );
}

function Row({ row, value, locked, onChange }) {
  const id = `field-${row.name}`;
  const label = (
    <label htmlFor={id} className="block text-sm text-muted">
      {row.label}
      {row.required && row.section === "needs_you" && <span className="ml-1 text-stop">required</span>}
    </label>
  );
  if (!row.editable || locked) {
    return (
      <li>
        {label}
        <p className="mt-0.5 whitespace-pre-wrap text-sm">
          {row.type === "input_file" && !row.value ? "Upload this yourself when the form is filled." : <Value row={{ ...row, value: value ?? row.value }} />}
        </p>
        {row.reason && <p className="mt-0.5 text-xs text-muted">Why: {row.reason}</p>}
      </li>
    );
  }
  const input = "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm";
  return (
    <li>
      {label}
      <div className="mt-1">
        {row.options.length ? (
          <select id={id} value={value ?? ""} onChange={(e) => onChange(row.name, e.target.value)} className={input}>
            <option value="" disabled>Choose an answer</option>
            {row.options.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        ) : row.type === "textarea" ? (
          <textarea id={id} rows={4} value={value ?? ""} onChange={(e) => onChange(row.name, e.target.value)} className={input} />
        ) : (
          <input id={id} type="text" value={value ?? ""} onChange={(e) => onChange(row.name, e.target.value)} className={input} />
        )}
      </div>
      {row.reason && <p className="mt-1 text-xs text-muted">Why: {row.reason}</p>}
    </li>
  );
}

function Value({ row }) {
  if (row.masked) return <span className="text-muted">On file</span>;
  return row.value ? String(row.value) : <span className="text-muted">Not answered</span>;
}

function StatusPill({ done, stale, needsYou }) {
  const [text, tone] =
    done === "approve" ? ["Approved", "bg-go text-white"]
    : done === "skip" ? ["Skipped", "bg-ink/10 text-ink"]
    : done === "changes" ? ["Changes requested", "bg-ink/10 text-ink"]
    : stale ? ["Replaced", "bg-ink/10 text-muted"]
    : needsYou ? ["Needs you", "bg-highlight/30 text-ink"]
    : ["Ready to approve", "bg-go/15 text-go"];
  return <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${tone}`}>{text}</span>;
}

function Count({ label, value, warn }) {
  return (
    <div className={`rounded-lg px-3 py-2 ${warn ? "bg-highlight/25" : "bg-paper"}`}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-lg font-semibold">{value}</dd>
    </div>
  );
}

function LockedNote({ done, decision }) {
  const text =
    done === "approve" ? `Approved${decision?.edited ? ` with ${decision.edited} edit${decision.edited === 1 ? "" : "s"}` : ""}. Moving on.`
    : done === "skip" ? "Skipped. Moving on."
    : done === "changes" ? "Changes requested. The new version appears below."
    : "Replaced by a newer version below.";
  return <span className={`font-medium ${done === "approve" ? "text-go" : "text-muted"}`}>{text}</span>;
}

function Button({ primary, ...props }) {
  return (
    <button
      type="button"
      {...props}
      className={`rounded-full px-4 py-1.5 font-medium disabled:opacity-40 ${
        primary ? "bg-go text-white" : "border border-line bg-surface hover:border-ink"
      }`}
    />
  );
}

/** The server's reason, if the error carries one ({"detail": ...}), in plain words. */
function errorText(message) {
  const detail = message?.match(/\{.*\}/s)?.[0];
  try {
    const parsed = JSON.parse(detail).detail;
    if (typeof parsed === "string") return parsed;
    if (parsed?.missing_required) return `Fill in: ${parsed.missing_required.join(", ")}.`;
    if (parsed?.problems) return parsed.problems.map((p) => `${p.label ?? p.name}: ${p.issue}`).join(" ");
  } catch {}
  return "Try again.";
}

const short = (text) => (text.length > 40 ? `${text.slice(0, 40)}…` : text);