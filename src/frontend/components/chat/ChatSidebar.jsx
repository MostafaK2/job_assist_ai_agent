"use client";

import { AuiIf, ThreadListItemPrimitive, ThreadListPrimitive } from "@assistant-ui/react";

/** List of conversations, with a "New chat" button at the top. */
export default function ChatSidebar({ onSelect }) {
  return (
    <ThreadListPrimitive.Root className="flex h-full flex-col gap-1 p-3">
      <ThreadListPrimitive.New asChild>
        <button
          type="button"
          onClick={onSelect}
          className="mb-2 flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm font-medium hover:border-ink"
        >
          <span aria-hidden="true" className="text-base leading-none">+</span>
          New chat
        </button>
      </ThreadListPrimitive.New>

      <h2 className="px-2 pt-2 pb-1 text-xs font-medium text-muted">Chats</h2>

      <AuiIf condition={(s) => s.threads.threadIds.length === 0}>
        <p className="px-2 text-sm text-muted">Your conversations will show up here.</p>
      </AuiIf>

      <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
        <ThreadListPrimitive.Items>{() => <ChatListItem onSelect={onSelect} />}</ThreadListPrimitive.Items>
      </div>
    </ThreadListPrimitive.Root>
  );
}

function ChatListItem({ onSelect }) {
  return (
    <ThreadListItemPrimitive.Root className="group relative flex items-center rounded-md hover:bg-paper data-active:bg-paper">
      <ThreadListItemPrimitive.Trigger
        onClick={onSelect}
        className="min-w-0 flex-1 truncate rounded-md px-2 py-2 pe-8 text-start text-sm group-data-active:font-medium"
      >
        <ThreadListItemPrimitive.Title fallback="New chat" />
      </ThreadListItemPrimitive.Trigger>
      <ThreadListItemPrimitive.Delete asChild>
        <button
          type="button"
          aria-label="Delete chat"
          className="absolute end-1 rounded p-1 text-muted opacity-0 hover:text-stop focus:opacity-100 group-hover:opacity-100 group-data-active:opacity-100"
        >
          <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4 fill-current">
            <path d="M8 2a1 1 0 0 0-1 1v1H4a1 1 0 0 0 0 2h.1l.8 10.1A2 2 0 0 0 6.9 18h6.2a2 2 0 0 0 2-1.9L15.9 6h.1a1 1 0 1 0 0-2h-3V3a1 1 0 0 0-1-1H8Zm1 2V4h2v0H9Zm-1 4a1 1 0 0 1 1 1v5a1 1 0 1 1-2 0V9a1 1 0 0 1 1-1Zm4 0a1 1 0 0 1 1 1v5a1 1 0 1 1-2 0V9a1 1 0 0 1 1-1Z" />
          </svg>
        </button>
      </ThreadListItemPrimitive.Delete>
    </ThreadListItemPrimitive.Root>
  );
}