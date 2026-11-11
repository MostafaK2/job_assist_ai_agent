"use client";

import {
  ActionBarPrimitive,
  AuiIf,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  SuggestionPrimitive,
  ThreadPrimitive,
  useAssistantTransportState
} from "@assistant-ui/react";
import MarkdownText from "@/components/chat/MarkdownText";

const isNewChat = (s) => s.thread.messages.length === 0;
const isRunning = (s) => s.thread.isRunning;
// Waiting for the reply to start: busy, and the reply has no text (or tool call) yet.
const replyHasStarted = (s) => {
  const last = s.thread.messages.at(-1);
  return last?.role === "assistant" && last.content?.some((p) => (p.type === "text" && p.text?.trim()) || p.type === "tool-call");
};
const isWaitingForReply = (s) => s.thread.isRunning && !replyHasStarted(s);

/** The conversation: messages, the welcome screen for new chats, and the message box. */
export default function Thread() {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
      <ThreadPrimitive.Viewport className="flex flex-1 flex-col overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pt-6">
          <AuiIf condition={isNewChat}>
            <Welcome />
          </AuiIf>

          <div className="flex flex-col gap-6 pb-6 empty:hidden">
            <ThreadPrimitive.Messages>
              {({ message }) => (message.role === "user" ? <UserMessage /> : <AssistantMessage />)}
            </ThreadPrimitive.Messages>
            <AuiIf condition={isWaitingForReply}>
                 <WaitingStatus />
            </AuiIf>
          </div>

          <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto flex flex-col gap-3 bg-paper pb-4">
            <ThreadPrimitive.ScrollToBottom asChild>
              <button
                type="button"
                aria-label="Scroll to the latest message"
                className="absolute -top-12 left-1/2 -translate-x-1/2 rounded-full border border-line bg-surface p-2 shadow-sm disabled:invisible"
              >
                <ArrowIcon className="h-4 w-4 rotate-180" />
              </button>
            </ThreadPrimitive.ScrollToBottom>
            <Composer />
            <AuiIf condition={isNewChat}>
              <SuggestionList />
            </AuiIf>
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

/** "Thinking…", or a notice while the backend condenses a long chat before replying. */
function WaitingStatus() {
  const summarizing = useAssistantTransportState((state) => state?.summarizing === true);
  return (
    <p role="status" className="animate-pulse text-muted motion-reduce:animate-none">
      {summarizing ? "Summarizing earlier messages so you can keep chatting…" : "Thinking…"}
    </p>
  );
}

function Welcome() {
  return (
    <div className="flex flex-1 flex-col justify-end pb-6">
      <h2 className="text-2xl font-bold tracking-tight">What are you looking for?</h2>
      <p className="mt-1 text-muted">Tell me the kind of jobs you want, or pick one of these to start.</p>
    </div>
  );
}

function SuggestionList() {
  return (
    <div className="flex flex-wrap gap-2">
      <ThreadPrimitive.Suggestions>
        {() => (
          <SuggestionPrimitive.Trigger send asChild>
            <button
              type="button"
              className="rounded-full border border-line bg-surface px-4 py-1.5 text-sm hover:border-ink"
            >
              <SuggestionPrimitive.Title />
            </button>
          </SuggestionPrimitive.Trigger>
        )}
      </ThreadPrimitive.Suggestions>
    </div>
  );
}

function Composer() {
  return (
    <ComposerPrimitive.Root className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-sm focus-within:border-ink">
      <ComposerPrimitive.Input
        autoFocus
        rows={1}
        placeholder="Ask about jobs, or tell me what to apply to…"
        aria-label="Message"
        className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 outline-none placeholder:text-muted focus-visible:outline-none"
      />
      <AuiIf condition={(s) => !isRunning(s)}>
        <ComposerPrimitive.Send asChild>
          <button
            type="submit"
            aria-label="Send message"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-ink text-white disabled:opacity-40"
          >
            <ArrowIcon className="h-4 w-4" />
          </button>
        </ComposerPrimitive.Send>
      </AuiIf>
      <AuiIf condition={isRunning}>
        <ComposerPrimitive.Cancel asChild>
          <button
            type="button"
            aria-label="Stop generating"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-ink text-white"
          >
            <span className="h-3 w-3 rounded-sm bg-white" />
          </button>
        </ComposerPrimitive.Cancel>
      </AuiIf>
    </ComposerPrimitive.Root>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end">
      <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl bg-ink px-4 py-2.5 text-white">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="group flex flex-col gap-2">
      <div className="leading-relaxed">
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
      </div>

      <MessagePrimitive.Error>
        <ErrorPrimitive.Root role="alert" className="rounded-md border border-stop/40 bg-stop/5 px-3 py-2 text-sm text-stop">
          <ErrorPrimitive.Message />
        </ErrorPrimitive.Root>
      </MessagePrimitive.Error>

      <ActionBarPrimitive.Root hideWhenRunning autohide="not-last" className="flex gap-1 text-muted">
        <ActionBarPrimitive.Copy asChild>
          <button type="button" className="rounded-md px-2 py-1 text-xs hover:bg-surface hover:text-ink">
            <AuiIf condition={(s) => s.message.isCopied}>Copied</AuiIf>
            <AuiIf condition={(s) => !s.message.isCopied}>Copy</AuiIf>
          </button>
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
    </MessagePrimitive.Root>
  );
}

function ArrowIcon({ className }) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" className={`fill-current ${className}`}>
      <path d="M10 3a1 1 0 0 1 .7.3l5 5a1 1 0 0 1-1.4 1.4L11 6.4V16a1 1 0 1 1-2 0V6.4L5.7 9.7a1 1 0 0 1-1.4-1.4l5-5A1 1 0 0 1 10 3Z" />
    </svg>
  );
}