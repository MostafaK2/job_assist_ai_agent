"use client";

import { useEffect, useState } from "react";
import ChatRuntimeProvider from "@/components/chat/ChatRuntimeProvider";
import ChatSidebar from "@/components/chat/ChatSidebar";
import Thread from "@/components/chat/Thread";

/** Conversation list on the left, the open conversation on the right. Opens on a new chat. */
export default function ChatApp() {
  const [showList, setShowList] = useState(false); // small screens only

  // Escape closes the conversation list on small screens.
  useEffect(() => {
    if (!showList) return;
    const onKey = (e) => e.key === "Escape" && setShowList(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [showList]);

  return (
    <ChatRuntimeProvider>
      <div className="relative flex h-full min-h-0">
        {showList && (
          <button
            type="button"
            aria-label="Close chats"
            onClick={() => setShowList(false)}
            className="absolute inset-0 z-10 bg-ink/30 md:hidden"
          />
        )}
        <aside
          className={`${showList ? "flex" : "hidden"} absolute inset-y-0 left-0 z-20 w-72 max-w-[85vw] flex-col border-r border-line bg-surface shadow-lg md:static md:flex md:shadow-none`}
          aria-label="Conversations"
        >
          <div className="flex justify-end px-3 pt-3 md:hidden">
            <button
              type="button"
              onClick={() => setShowList(false)}
              className="rounded-md px-2 py-1 text-sm text-muted hover:bg-paper hover:text-ink"
            >
              Close
            </button>
          </div>
          <ChatSidebar onSelect={() => setShowList(false)} />
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <div className="border-b border-line px-4 py-2 md:hidden">
            <button
              type="button"
              onClick={() => setShowList((v) => !v)}
              aria-expanded={showList}
              className="rounded-md border border-line bg-surface px-3 py-1.5 text-sm"
            >
              Chats
            </button>
          </div>
          <div className="min-h-0 flex-1">
            <Thread />
          </div>
        </section>
      </div>
    </ChatRuntimeProvider>
  );
}