"use client";

import { useEffect, useRef } from "react";
import {
  AssistantRuntimeProvider,
  AuiConfig,
  Suggestions,
  unstable_createMessageConverter as createMessageConverter,
  useAssistantTransportRuntime,
  useAui,
  useRemoteThreadListRuntime,
} from "@assistant-ui/react";
import { convertLangChainMessages } from "@assistant-ui/react-langgraph";
import { loadThreadMessages, threadListAdapter } from "@/lib/threads";

// The Python agent's messages are LangChain messages; this turns them into chat bubbles.
const langChainMessages = createMessageConverter(convertLangChainMessages);

/** Shows the backend's messages, plus the user's just-sent message right away (before the server replies). */
function converter(state, connection) {
  const pending = connection.pendingCommands.flatMap((command) => {
    if (command.type !== "add-message" || command.message.role !== "user") return [];
    const text = command.message.parts.map((p) => (p.type === "text" ? p.text : "")).join("\n");
    return [{ type: "human", ...(command.message.id && { id: command.message.id }), content: [{ type: "text", text }] }];
  });

  return {
    messages: langChainMessages.toThreadMessages([...(state.messages ?? []), ...pending]),
    isRunning: connection.isSending || false,
  };
}

const EMPTY_STATE = { messages: [], summarizing: false };

/** One chat conversation, talking to POST /api/assistant on the Python backend. */
function useJobAssistRuntime() {
  const runtime = useAssistantTransportRuntime({
    api: "/api/assistant", // proxied to the backend by next.config.mjs
    protocol: "assistant-transport",
    initialState: EMPTY_STATE,
    converter,
    headers: { "Content-Type": "application/json" },
  });
  useSavedMessages(runtime);
  return runtime;
}

/**
 * Opening a saved chat: load its messages from the backend (GET /api/threads/{id}/messages).
 * Each chat gets its own runtime, so this runs once per chat you open.
 */
function useSavedMessages(runtime) {
  const aui = useAui();
  // The chat's server id when this chat was opened. A brand-new chat has none yet; it gets
  // one when its first message is sent, and must not load anything (it would wipe the reply).
  const openedWithId = useRef(aui.threadListItem.getState().remoteId);

  useEffect(() => {
    const remoteId = openedWithId.current;
    if (!remoteId) return;
    let cancelled = false;
    loadThreadMessages(remoteId)
      .then((messages) => {
        const thread = runtime.thread.getState();
        // Don't overwrite anything the user started in the meantime.
        if (cancelled || thread.isRunning || thread.messages.length > 0) return;
        runtime.thread.importExternalState({ ...EMPTY_STATE, messages });
      })
      .catch((error) => console.warn("Couldn't load this chat's messages:", error.message));
    return () => {
      cancelled = true;
    };
  }, [runtime]);
}

const config = AuiConfig({
  suggestions: Suggestions([
    { title: "Apply to the most recent jobs", prompt: "Apply to the most recent jobs that match my profile." },
    { title: "Find remote backend roles", prompt: "Find remote backend engineering roles that fit me." },
    { title: "What can you do?", prompt: "What can you help me with?" },
  ]),
});

export default function ChatRuntimeProvider({ children }) {
  const runtime = useRemoteThreadListRuntime({
    runtimeHook: useJobAssistRuntime,
    adapter: threadListAdapter, // the sidebar, saved in Postgres (lib/threads.js)
  });

  return (
    <AssistantRuntimeProvider runtime={runtime} config={config}>
      {children}
    </AssistantRuntimeProvider>
  );
}