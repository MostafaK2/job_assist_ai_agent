"use client";

import { useEffect, useRef, useState } from "react";
import { useAssistantTransportSendCommand, useAssistantTransportState, useAuiState } from "@assistant-ui/react";

/**
 * The fill_application result: fills the approved application in the user's own Chrome.
 * On first show it asks the backend for the fill plan (POST /api/fills/{id}/plan: works ONCE, so
 * reloading the chat never reopens the form), fetches the resume, and hands both to the Job Assist
 * extension, which opens the Greenhouse page in a new tab and fills it. Progress comes back over a
 * long-lived connection. The user submits on the real page, then presses "I submitted it" here.
 */
export const EXTENSION_ID = process.env.NEXT_PUBLIC_EXTENSION_ID || "nkkmkjenpmkclkbephgefeajnomcfmgp";
const PORT_NAME = "job-assist-fill";
const startedHere = new Set(); // fills this page already started (a card can mount twice)

const extension = () => (typeof chrome !== "undefined" && chrome.runtime?.connect ? chrome.runtime : null);

function ping() {
  const rt = extension();
  if (!rt) return Promise.resolve(false);
  return new Promise((resolve) => {
    try {
      rt.sendMessage(EXTENSION_ID, { type: "ping" }, (reply) => resolve(!rt.lastError && Boolean(reply?.ok)));
    } catch {
      resolve(false);
    }
  });
}

async function toBase64(blob) {
  const url = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
  return String(url).split(",", 2)[1];
}

async function apiError(res) {
  try {
    const body = await res.json();
    return typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export default function FillCard({ toolCallId, artifact, result }) {
  if (!artifact) {
    return result === undefined
      ? <p className="animate-pulse text-sm text-muted motion-reduce:animate-none">Opening the form…</p>
      : null;
  }
  return <FillBody key={artifact.fill_id} toolCallId={toolCallId} artifact={artifact} />;
}

function FillBody({ toolCallId, artifact }) {
  const sendCommand = useAssistantTransportSendCommand();
  const threadId = useAuiState((s) => s.threadListItem?.remoteId);
  const isRunning = useAuiState((s) => s.thread.isRunning);
  // The saved outcome for this fill, if any (survives reloading the chat).
  const outcome = useAuiState((s) =>
    s.thread.messages.find((m) => m.metadata?.custom?.fillEvent?.toolCallId === toolCallId)
  )?.metadata.custom.fillEvent;
  const failure = useAssistantTransportState((s) => s?.failedCommands?.findLast((f) => f.toolCallId === toolCallId));

  const [phase, setPhase] = useState({ name: "checking" }); // checking | no-extension | filling | already | error
  const [progress, setProgress] = useState(null);
  const [report, setReport] = useState(null);
  const [sent, setSent] = useState(null);
  const portRef = useRef(null);
  const fillId = artifact.fill_id;

  function connect() {
    portRef.current?.disconnect();
    const port = extension().connect(EXTENSION_ID, { name: PORT_NAME });
    port.onMessage.addListener((event) => {
      if (event.type === "opened" || event.type === "started") setPhase({ name: "filling" });
      if (event.type === "started") setProgress({ done: 0, total: event.total });
      if (event.type === "progress") setProgress({ done: event.done, total: event.total });
      if (event.type === "report") setReport(event);
      if (event.type === "error") setPhase({ name: "error", message: event.message });
    });
    port.onDisconnect.addListener(() => { if (portRef.current === port) portRef.current = null; });
    portRef.current = port;
    return port;
  }

  async function begin(again) {
    if (!again && startedHere.has(fillId)) return;
    startedHere.add(fillId);
    if (!(await ping())) return setPhase({ name: "no-extension" });
    const res = await fetch(`/api/fills/${fillId}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ threadId, again }),
    });
    if (res.status === 409) {
      setPhase({ name: "already", message: await apiError(res) });
      connect().postMessage({ type: "attach", fillId });   // show what happened earlier, if the extension still knows
      return;
    }
    if (!res.ok) return setPhase({ name: "error", message: await apiError(res) });
    const plan = await res.json();
    let resume = null;
    if (plan.resume) {
      const file = await fetch(`/api/fills/${fillId}/resume?threadId=${encodeURIComponent(threadId)}`);
      if (file.ok) resume = { base64: await toBase64(await file.blob()), filename: plan.resume.filename, type: "application/pdf" };
    }
    setReport(null);
    setProgress(null);
    setPhase({ name: "filling" });
    connect().postMessage({ type: "start", plan, resume });
  }

  useEffect(() => {
    // Started from a timer, so a card that React mounts twice (dev mode) starts once; begin()
    // also checks startedHere, and the backend serves the plan only once.
    const timer = outcome ? null : setTimeout(() => {
      begin(false).catch((err) => setPhase({ name: "error", message: err.message }));
    }, 0);
    return () => {
      clearTimeout(timer);
      portRef.current?.disconnect();
    };
    // Runs once per card.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function fillAgain() {
    setPhase({ name: "checking" });
    begin(true).catch((err) => setPhase({ name: "error", message: err.message }));
  }

  const failed = Boolean(sent && !outcome && failure && failure.at >= sent.at);
  const done = outcome?.event ?? (failed ? null : sent?.event);
  const decide = (event) => {
    setSent({ event, at: Date.now() });
    sendCommand({ type: "fill-event", toolCallId, event });
  };

  return (
    <section aria-label="Fill application" className="my-3 overflow-hidden rounded-2xl border border-line bg-surface">
      <header className="flex items-start justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <a href={artifact.url} target="_blank" rel="noopener noreferrer" className="font-semibold hover:underline">
            {artifact.job.title}
          </a>
          <p className="text-sm text-muted">{artifact.job.id}</p>
        </div>
        <Pill done={done} phase={phase.name} report={report} />
      </header>

      <div className="border-t border-line px-4 py-3 text-sm">
        <Status phase={phase} progress={progress} report={report} done={done} />
      </div>

      {!done && (
        <footer className="flex flex-col gap-2 border-t border-line bg-paper px-4 py-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Button primary onClick={() => decide("submitted")} disabled={isRunning}>I submitted it</Button>
            <Button onClick={() => decide("skipped")} disabled={isRunning}>Skip this job</Button>
            <Button onClick={() => fillAgain()}
                    disabled={isRunning || phase.name === "checking"}>
              Fill again
            </Button>
          </div>
          <span className="text-xs text-muted">Nothing is submitted for you. Check the form in the new tab and press Submit there.</span>
          {failed && <p role="alert" className="text-xs text-stop">That didn&apos;t go through. Try again.</p>}
        </footer>
      )}
    </section>
  );
}

function Status({ phase, progress, report, done }) {
  if (done === "submitted") return <p className="font-medium text-go">Submitted. Moving on.</p>;
  if (done === "skipped") return <p className="text-muted">Skipped. Moving on.</p>;
  if (phase.name === "no-extension") {
    return (
      <div className="flex flex-col gap-1">
        <p className="font-medium">Install the Job Assist extension to fill this form.</p>
        <p className="text-muted">
          In Chrome, open chrome://extensions, turn on Developer mode, choose Load unpacked and pick the
          src/extension folder. Then press Fill again.
        </p>
      </div>
    );
  }
  if (phase.name === "error") return <p className="text-stop">{phase.message}</p>;
  if (report) {
    const needs = [...report.needs.map((n) => n.label), ...report.failed.map((f) => f.label)];
    return (
      <div className="flex flex-col gap-1">
        <p>
          Filled <b>{report.filled}</b> of {report.total}
          {report.by_assistant ? ` · ${report.by_assistant} written by the assistant` : ""}.
        </p>
        {needs.length > 0 && (
          <div>
            <p className="font-medium text-stop">Needs you in the form:</p>
            <ul className="ml-5 list-disc">{needs.map((label) => <li key={label}>{label}</li>)}</ul>
          </div>
        )}
        <p className="text-muted">Check the tab, fix anything marked red, then press Submit there.</p>
      </div>
    );
  }
  if (phase.name === "already") return <p className="text-muted">{phase.message}. Press Fill again to open it once more.</p>;
  if (progress) return <p>Filling in a new tab: {progress.done} of {progress.total}…</p>;
  return <p className="animate-pulse text-muted motion-reduce:animate-none">Opening the form in a new Chrome tab…</p>;
}

function Pill({ done, phase, report }) {
  const [text, tone] =
    done === "submitted" ? ["Submitted", "bg-go text-white"]
    : done === "skipped" ? ["Skipped", "bg-ink/10 text-ink"]
    : phase === "no-extension" || phase === "error" ? ["Needs attention", "bg-highlight/30 text-ink"]
    : report ? ["Ready to submit", "bg-go/15 text-go"]
    : phase === "already" ? ["Opened", "bg-ink/10 text-ink"]
    : ["Filling", "bg-ink/10 text-ink"];
  return <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${tone}`}>{text}</span>;
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