"use client";

import {
  AssistantRuntimeProvider,
  AuiConfig,
  Suggestions,
  unstable_createMessageConverter as createMessageConverter,
  useAssistantTransportRuntime,
  useRemoteThreadListRuntime,
} from "@assistant-ui/react";
import { convertLangChainMessages } from "@assistant-ui/react-langgraph";
import { threadListAdapter } from "@/lib/threads";

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

/** One chat conversation, talking to POST /api/assistant on the Python backend. */
function useJobAssistRuntime() {
  return useAssistantTransportRuntime({
    api: "/api/assistant", // proxied to the backend by next.config.mjs
    protocol: "assistant-transport",
    initialState: { messages: [], summarizing: false },
    converter,
    headers: { "Content-Type": "application/json" },
  });
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
    adapter: threadListAdapter,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime} config={config}>
      {children}
    </AssistantRuntimeProvider>
  );
}