// Runs on Greenhouse application pages. If this tab was opened by Job Assist with a fill plan,
// fill the form, show a small panel, and report back (labels only, never values) to the chat
// through background.js. It never submits: while it's filling, submitting is blocked; after,
// the page is yours.
(() => {
  const JA = globalThis.JA;
  const FORM = "#application-form, #application_form, form[action*='application'], input#first_name, [name='job_application[first_name]']";

  const send = (event) => chrome.runtime.sendMessage({ type: "event", event }).catch(() => {});

  function base64ToBytes(b64) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }

  function findResumeInput(resume) {
    const byName = document.getElementById(resume.name) ?? document.querySelector(`input[type=file][name="${CSS.escape(resume.name)}"]`);
    if (byName?.type === "file") return byName;
    return [...document.querySelectorAll("input[type=file]")].find((i) =>
      /resume|cv/i.test(`${i.id} ${i.name} ${i.closest("[class*='field'], fieldset, div")?.innerText ?? ""}`)) ?? null;
  }

  // ---------------------------------------------------------------- panel (shadow DOM: page styles can't touch it)
  function makePanel(job) {
    const host = document.createElement("div");
    host.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:2147483647;";
    const root = host.attachShadow({ mode: "closed" });
    root.innerHTML = `
      <style>
        .p{font:13px/1.45 system-ui,sans-serif;color:#0f172a;background:#fff;border:1px solid #cbd5e1;border-radius:14px;
           box-shadow:0 8px 24px rgba(15,23,42,.18);width:300px;padding:12px 14px}
        .h{display:flex;justify-content:space-between;align-items:center;font-weight:600}
        .x{border:0;background:none;font-size:16px;cursor:pointer;color:#64748b}
        .bar{height:6px;background:#e2e8f0;border-radius:6px;margin:8px 0;overflow:hidden}
        .bar i{display:block;height:100%;width:0;background:#16a34a;transition:width .2s}
        ul{margin:4px 0 0;padding-left:18px;max-height:160px;overflow:auto} li{margin:2px 0}
        .s{color:#475569}.w{color:#b45309}.f{color:#b91c1c}.n{font-size:12px;color:#64748b;margin-top:8px}
      </style>
      <div class="p" role="status" aria-live="polite">
        <div class="h"><span>Job Assist</span><button class="x" aria-label="Hide">×</button></div>
        <div class="s" id="job"></div>
        <div class="bar"><i id="bar"></i></div>
        <div id="line">Starting…</div>
        <div id="lists"></div>
        <div class="n">Nothing is submitted. Check the form, then press Submit yourself.</div>
      </div>`;
    root.querySelector("#job").textContent = job?.title ?? "";
    root.querySelector(".x").onclick = () => host.remove();
    document.documentElement.appendChild(host);
    const el = (id) => root.querySelector(`#${id}`);
    return {
      progress(done, total) {
        el("bar").style.width = `${Math.round((100 * done) / Math.max(total, 1))}%`;
        el("line").textContent = `Filling ${done} of ${total}…`;
      },
      finish(report) {
        el("bar").style.width = "100%";
        el("line").textContent = `Filled ${report.filled} of ${report.total}` +
          (report.by_assistant ? ` (${report.by_assistant} written by the assistant)` : "") + ".";
        const lists = el("lists");
        lists.textContent = "";
        const add = (title, cls, items) => {
          if (!items.length) return;
          const h = document.createElement("div");
          h.className = cls;
          h.textContent = title;
          const ul = document.createElement("ul");
          for (const t of items) { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); }
          lists.append(h, ul);
        };
        add("Needs you:", "f", [...report.needs.map((n) => n.label), ...report.failed.map((f) => `${f.label} (${f.reason})`)]);
      },
    };
  }

  // ---------------------------------------------------------------- the fill
  async function run(plan, resume) {
    const panel = makePanel(plan.job);
    // While filling, nothing may submit the form (e.g. a stray Enter). Removed when done.
    const block = (e) => { e.preventDefault(); e.stopImmediatePropagation(); };
    document.addEventListener("submit", block, true);

    const fields = plan.fields ?? [];
    const total = fields.length + (plan.resume ? 1 : 0);
    const report = { type: "report", total, filled: 0, by_assistant: 0, failed: [], needs: [...(plan.unanswered ?? [])] };
    send({ type: "started", total });
    let done = 0;
    try {
      if (plan.resume && resume?.base64) {
        const input = findResumeInput(plan.resume);
        const res = input
          ? await JA.setFile(input, { bytes: base64ToBytes(resume.base64), filename: resume.filename, type: resume.type })
          : { ok: false, reason: "no upload field found" };
        if (res.ok) { report.filled += 1; JA.mark(input.closest("[class*='field'], fieldset") ?? input.parentElement, "ok"); }
        else report.failed.push({ name: plan.resume.name, label: plan.resume.label, reason: res.reason });
        panel.progress(++done, total);
      }
      for (const spec of fields) {
        const found = JA.find(spec);
        const res = found ? await JA.fillOne(found, spec.value, spec) : { ok: false, reason: "field not found on the page" };
        if (res.ok) {
          report.filled += 1;
          if (spec.source === "model") report.by_assistant += 1;
          JA.mark(found.el, spec.source === "model" ? "assistant" : "ok");
        } else {
          if (found) JA.mark(found.el, "fail");
          report.failed.push({
            name: spec.name, label: spec.label, reason: res.reason, private: !!spec.private, required: !!spec.required,
            ...(spec.private ? {} : { candidates: res.candidates ?? [], tried: res.tried ?? [] }),
          });
        }
        panel.progress(++done, total);
        send({ type: "progress", done, total });
        await JA.sleep(60);
      }
    } finally {
      document.removeEventListener("submit", block, true);
    }
    panel.finish(report);
    send(report);
  }

  (async () => {
    if (!(await JA.waitFor(() => document.querySelector(FORM), 15000, 250))) return;   // not an application form
    const got = await chrome.runtime.sendMessage({ type: "get-plan" }).catch(() => null);
    if (!got?.plan) return;                       // a normal visit, not opened by Job Assist
    await JA.waitFor(() => document.readyState === "complete", 10000, 100);
    await JA.sleep(1200);                         // let the page's React finish hydrating
    run(got.plan, got.resume);
  })();
})();
