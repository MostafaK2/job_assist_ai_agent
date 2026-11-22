// Job Assist extension: the go-between for the chat page and the Greenhouse tab.
//
// Chat page (only http://localhost:3000, see externally_connectable in manifest.json):
//   sendMessage {type: "ping"}                      -> {ok, version}   (is the extension installed?)
//   connect(name "job-assist-fill"), then post:
//     {type: "start", plan, resume}   open the Greenhouse tab and fill it with this plan
//     {type: "attach", fillId}        follow an earlier fill (events so far are replayed)
//   It receives the fill's events: opened, started, progress, report, error.
// Greenhouse tab (content.js):
//   {type: "get-plan"}  -> its plan, once      {type: "event", event} -> forwarded to the chat page
//
// State lives in chrome.storage.session (survives this service worker going to sleep).
const GREENHOUSE_HOSTS = new Set(["job-boards.greenhouse.io", "boards.greenhouse.io"]);
const PORT_NAME = "job-assist-fill";
const MAX_EVENTS = 50;
const ports = new Map(); // fillId -> port (in memory; the chat page re-attaches if it's lost)

const store = chrome.storage.session;
const get = async (key) => (await store.get(key))[key];

async function emit(fillId, event) {
  const key = `fill:${fillId}`;
  const fill = (await get(key)) ?? { events: [] };
  fill.events = [...fill.events, event].slice(-MAX_EVENTS);
  await store.set({ [key]: fill });
  try { ports.get(fillId)?.postMessage(event); } catch { ports.delete(fillId); }
}

function isGreenhouse(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && GREENHOUSE_HOSTS.has(u.hostname);
  } catch {
    return false;
  }
}

async function start(plan, resume) {
  const fillId = plan.fill_id;
  if (!isGreenhouse(plan.url)) return emit(fillId, { type: "error", message: "Not a Greenhouse application page." });
  const tab = await chrome.tabs.create({ url: plan.url, active: true });
  await store.set({
    [`tab:${tab.id}`]: { fillId, plan, resume, given: false },
    [`fill:${fillId}`]: { tabId: tab.id, events: [] },
  });
  await emit(fillId, { type: "opened" });
}

chrome.runtime.onMessageExternal.addListener((msg, _sender, reply) => {
  if (msg?.type === "ping") reply({ ok: true, version: chrome.runtime.getManifest().version });
});

chrome.runtime.onConnectExternal.addListener((port) => {
  if (port.name !== PORT_NAME) return port.disconnect();
  let fillId = null;
  port.onMessage.addListener(async (msg) => {
    if (msg?.type === "start" && msg.plan?.fill_id) {
      fillId = msg.plan.fill_id;
      ports.set(fillId, port);
      await start(msg.plan, msg.resume);
    } else if (msg?.type === "attach" && msg.fillId) {
      fillId = msg.fillId;
      ports.set(fillId, port);
      for (const event of (await get(`fill:${fillId}`))?.events ?? []) port.postMessage({ ...event, replay: true });
    }
  });
  port.onDisconnect.addListener(() => {
    if (fillId && ports.get(fillId) === port) ports.delete(fillId);
  });
});

// From the Greenhouse tab's content script.
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  const tabId = sender.tab?.id;
  if (tabId == null) return;
  (async () => {
    const key = `tab:${tabId}`;
    const job = await get(key);
    if (!job) return reply(null);
    if (msg?.type === "get-plan") {
      if (job.given) return reply(null);        // once: a reload of the tab doesn't fill again
      await store.set({ [key]: { ...job, given: true, resume: null } });
      return reply({ plan: job.plan, resume: job.resume });
    }
    if (msg?.type === "event" && msg.event?.type) {
      await emit(job.fillId, msg.event);
      return reply(true);
    }
    reply(null);
  })();
  return true; // reply asynchronously
});
