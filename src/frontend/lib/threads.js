// The chat list (sidebar), saved by the Python backend at /api/threads.
// assistant-ui calls these methods; each conversation's id comes from the server.
import { createAssistantStream } from "assistant-stream";
import { apiFetch } from "@/lib/api";

const TITLE_MAX_CHARS = 60;
const threadUrl = (id) => `/api/threads/${encodeURIComponent(id)}`;

// Backend thread → the shape assistant-ui expects.
function toMetadata(thread) {
  return {
    status: thread.archived ? "archived" : "regular",
    remoteId: thread.id,
    title: thread.title ?? undefined,
    lastMessageAt: new Date(thread.updated_at),
  };
}

function titleFrom(messages) {
  const text = messages
    ?.find((m) => m.role === "user")
    ?.content?.find((part) => part.type === "text")
    ?.text?.trim();
  return text ? text.replace(/\s+/g, " ").slice(0, TITLE_MAX_CHARS) : "";
}

// One object for the whole app: assistant-ui needs the same adapter on every render.
export const threadListAdapter = {
  async list() {
    try {
      const [active, archived] = await Promise.all([
        apiFetch("/api/threads"),
        apiFetch("/api/threads?archived=true"),
      ]);
      return { threads: [...active, ...archived].map(toMetadata) };
    } catch (error) {
      // Backend down or unreachable: show an empty sidebar instead of failing the chat page.
      // The list loads again on the next page load.
      console.warn("Couldn't load your chats:", error.message);
      return { threads: [] };
    }
  },

  // Called when the first message of a new chat is sent. The server creates the
  // conversation and its id becomes the threadId sent to /api/assistant.
  async initialize() {
    const thread = await apiFetch("/api/threads", { method: "POST" });
    return { remoteId: thread.id };
  },

  async fetch(remoteId) {
    return toMetadata(await apiFetch(threadUrl(remoteId)));
  },

  async rename(remoteId, title) {
    await apiFetch(threadUrl(remoteId), { method: "PATCH", body: { title } });
  },

  async archive(remoteId) {
    await apiFetch(threadUrl(remoteId), { method: "PATCH", body: { archived: true } });
  },

  async unarchive(remoteId) {
    await apiFetch(threadUrl(remoteId), { method: "PATCH", body: { archived: false } });
  },

  async delete(remoteId) {
    await apiFetch(threadUrl(remoteId), { method: "DELETE" });
  },

  // Name the chat after the first thing the user asked. Saved before the stream ends,
  // as assistant-ui requires, so a refresh shows the same title.
  async generateTitle(remoteId, messages) {
    const title = titleFrom(messages);
    if (title) await this.rename(remoteId, title);
    return createAssistantStream((controller) => {
      if (title) controller.appendText(title);
    });
  },
};