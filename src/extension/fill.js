// Finding a form field on the page and putting a value in it, the way a person would
// (so React-based forms like Greenhouse's notice the change). Never clicks Submit.
//
//   JA.find(spec)                    -> {el, kind} | null    kind: text | select | combo | group | file
//   JA.fillOne(found, value, spec)   -> {ok: true, shown} | {ok: false, reason, candidates?, tried?}
//   JA.setFile(input, {bytes, filename, type})
//   JA.mark(el, "ok" | "assistant" | "fail")
(() => {
  const JA = (globalThis.JA ??= {});
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  JA.sleep = sleep;

  /** Wait until fn() returns something truthy (polls), or give up after `ms`. */
  JA.waitFor = async (fn, ms = 3000, every = 100) => {
    const end = Date.now() + ms;
    for (;;) {
      const v = fn();
      if (v) return v;
      if (Date.now() > end) return null;
      await sleep(every);
    }
  };

  const visible = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
  const labelText = (s) => JA.norm(String(s ?? "").replace(/\*/g, " ").replace(/\(required\)/gi, " "));

  // ---------------------------------------------------------------- finding fields
  function kindOf(el) {
    if (!el) return null;
    const tag = el.tagName;
    if (tag === "FIELDSET" || el.getAttribute("role") === "group" || el.getAttribute("role") === "radiogroup") return "group";
    if (tag === "SELECT") return "select";
    if (tag === "TEXTAREA") return "text";
    if (tag !== "INPUT") return null;
    const type = (el.type || "text").toLowerCase();
    if (type === "file") return "file";
    if (type === "checkbox" || type === "radio") return "group";
    if (el.getAttribute("role") === "combobox" || el.closest("[class*='select__control'], [class*='select-control']")) return "combo";
    if (type === "hidden") return null;
    return "text";
  }

  /** A react-select keeps a hidden <input name=...> next to the real combobox <input>. */
  function upgrade(el) {
    if (el?.tagName === "INPUT" && el.type === "hidden") {
      const box = el.closest("[class*='select__container'], [class*='select-container']") ?? el.parentElement;
      return box?.querySelector("input[role='combobox']") ?? null;
    }
    if (el?.tagName === "INPUT" && ["checkbox", "radio"].includes(el.type)) {
      return el.closest("fieldset, [role='group'], [role='radiogroup']") ?? el.parentElement?.parentElement ?? el;
    }
    return el;
  }

  function byLabel(label) {
    const want = labelText(label);
    if (!want) return null;
    const short = want.slice(0, 80);
    const nodes = [...document.querySelectorAll("label, legend, [id$='-label'], [class*='label']")];
    const match = nodes.find((n) => labelText(n.innerText) === want) ??
      nodes.find((n) => { const t = labelText(n.innerText); return t.length > 3 && (t.startsWith(short) || short.startsWith(t)); });
    if (!match) return null;
    if (match.tagName === "LEGEND") return match.closest("fieldset");
    const forId = match.getAttribute("for");
    if (forId) return document.getElementById(forId);
    const labelled = document.querySelector(`[aria-labelledby~="${CSS.escape(match.id || "-")}"]`);
    return labelled ?? match.querySelector("input, select, textarea") ??
      match.parentElement?.querySelector("input:not([type=hidden]), select, textarea, fieldset");
  }

  JA.find = (spec) => {
    const name = String(spec.name ?? "");
    const tries = [
      () => name && document.getElementById(name),
      () => name && document.querySelector(`[name="${CSS.escape(name)}"], [name="${CSS.escape(name)}[]"]`),
      () => name && document.querySelector(`[name$="[${CSS.escape(name)}]"]`),   // older boards: job_application[first_name]
      () => byLabel(spec.label),
    ];
    for (const t of tries) {
      const el = upgrade(t());
      const kind = kindOf(el);
      if (kind) return { el, kind };
    }
    return null;
  };

  // ---------------------------------------------------------------- setting values
  function setNative(el, value) {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  async function fillText(el, value) {
    el.focus();
    setNative(el, String(value));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new FocusEvent("blur"));
    el.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    await sleep(30);
    return el.value === String(value) ? { ok: true, shown: el.value } : { ok: false, reason: "the page didn't keep the value" };
  }

  async function fillSelect(el, value) {
    const options = [...el.options].filter((o) => o.value !== "");
    const res = JA.pick(value, options.map((o) => o.text));
    if (!res.option) return { ok: false, reason: "no matching option", candidates: res.candidates };
    const opt = options.find((o) => o.text === res.option);
    el.value = opt.value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return el.value === opt.value ? { ok: true, shown: opt.text } : { ok: false, reason: "the page didn't keep the choice" };
  }

  function groupInputs(container) {
    return [...container.querySelectorAll("input[type=checkbox], input[type=radio]")].map((input) => ({
      input,
      text: (input.labels?.[0]?.innerText ?? input.closest("label")?.innerText ?? input.value ?? "").trim(),
    }));
  }

  async function fillGroup(container, value) {
    const items = groupInputs(container);
    const wanted = Array.isArray(value) ? value : [value];
    const shown = [];
    for (const v of wanted) {
      const res = JA.pick(v, items.map((i) => i.text));
      if (!res.option) return { ok: false, reason: "no matching option", candidates: res.candidates };
      const item = items.find((i) => i.text === res.option);
      if (!item.input.checked) item.input.click();
      await sleep(30);
      if (!item.input.checked) return { ok: false, reason: "the page didn't keep the choice" };
      shown.push(item.text);
    }
    return { ok: true, shown: shown.join(", ") };
  }

  // -------- combobox (react-select: Greenhouse's "Select..." dropdowns, incl. search-as-you-type)
  const controlOf = (input) => input.closest("[class*='select__control'], [class*='select-control']") ?? input.parentElement;
  const containerOf = (input) => input.closest("[class*='select__container'], [class*='select-container']") ?? controlOf(input).parentElement;

  function optionNodes(input) {
    const listId = input.getAttribute("aria-controls") || input.getAttribute("aria-owns");
    const list = listId && document.getElementById(listId);
    const scope = list ?? containerOf(input) ?? document;
    let nodes = [...scope.querySelectorAll("[role='option']")].filter(visible);
    if (!nodes.length) nodes = [...document.querySelectorAll("[role='option']")].filter(visible); // menu in a portal
    return nodes;
  }

  /** Options once they've appeared and stopped changing (search fields load them from a server). */
  async function settledOptions(input, ms) {
    const end = Date.now() + ms;
    let last = "", stableSince = Date.now();
    for (;;) {
      const nodes = optionNodes(input);
      const key = nodes.map((n) => n.innerText).join("|");
      if (key !== last) { last = key; stableSince = Date.now(); }
      if (nodes.length && Date.now() - stableSince > 350) return nodes;
      if (Date.now() > end) return nodes;
      await sleep(100);
    }
  }

  function mouse(el, type) {
    el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, button: 0, view: window }));
  }

  async function openCombo(input) {
    input.focus();
    mouse(controlOf(input), "mousedown");
    await sleep(120);
    if (!optionNodes(input).length) {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", code: "ArrowDown", keyCode: 40, bubbles: true }));
      await sleep(120);
    }
  }

  function closeCombo(input) {
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, bubbles: true }));
    input.blur();
  }

  /** Searches to try for a search-as-you-type field: full value, then shorter forms. */
  JA.queries = (value) => {
    const v = String(value).trim();
    const out = [v, v.split(",")[0].trim(), v.split(/\s+/).slice(0, 2).join(" "), v.split(/\s+/)[0]];
    return [...new Set(out.filter((q) => q.length >= 2))];
  };

  async function fillCombo(input, value, spec = {}) {
    await openCombo(input);
    let nodes = await settledOptions(input, 900);
    let res = nodes.length ? JA.pick(value, nodes.map((n) => n.innerText.trim())) : { option: null, candidates: [] };
    const tried = [];
    if (!res.option) {
      for (const q of spec.queries ?? JA.queries(value)) {
        tried.push(q);
        setNative(input, q);
        nodes = await settledOptions(input, 4000);
        res = JA.pick(value, nodes.map((n) => n.innerText.trim()));
        if (res.option) break;
      }
    }
    if (!res.option) {
      const candidates = res.candidates?.length ? res.candidates : nodes.map((n) => n.innerText.trim()).slice(0, 8);
      setNative(input, "");
      closeCombo(input);
      return { ok: false, reason: "no clear option", candidates, tried };
    }
    const node = nodes.find((n) => n.innerText.trim() === res.option);
    mouse(node, "mouseover");
    mouse(node, "mousedown");
    mouse(node, "mouseup");
    mouse(node, "click");
    await sleep(120);
    const shownText = (containerOf(input)?.innerText ?? "").trim();
    if (!JA.norm(shownText).includes(JA.norm(res.option))) {
      closeCombo(input);
      return { ok: false, reason: "the page didn't keep the choice", candidates: [res.option] };
    }
    input.blur();
    return { ok: true, shown: res.option };
  }

  JA.fillOne = async (found, value, spec = {}) => {
    try {
      switch (found.kind) {
        case "text": return await fillText(found.el, value);
        case "select": return await fillSelect(found.el, value);
        case "group": return await fillGroup(found.el, value);
        case "combo": return await fillCombo(found.el, value, spec);
        default: return { ok: false, reason: `can't fill a ${found.kind} field` };
      }
    } catch (err) {
      return { ok: false, reason: `error: ${err?.message ?? err}` };
    }
  };

  JA.setFile = async (input, file) => {
    const data = new DataTransfer();
    data.items.add(new File([file.bytes], file.filename, { type: file.type || "application/pdf" }));
    input.files = data.files;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(200);
    return input.files?.length ? { ok: true, shown: file.filename } : { ok: false, reason: "the page refused the file" };
  };

  /** Outline what was done: green = from your profile, amber = written by the assistant, red = needs you. */
  JA.mark = (el, status) => {
    // react-select forces "outline: 0 !important" on its control, so outline the box around it.
    const target = el?.tagName === "INPUT" && el.getAttribute("role") === "combobox" ? containerOf(el) : el;
    if (!target?.style) return;
    const color = { ok: "#16a34a", assistant: "#d97706", fail: "#dc2626" }[status];
    target.style.outline = `2px solid ${color}`;
    target.style.outlineOffset = "2px";
  };
})();
