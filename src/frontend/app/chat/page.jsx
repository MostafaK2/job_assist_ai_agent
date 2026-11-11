import ChatApp from "@/components/chat/ChatApp";

export const metadata = { title: "Chat" };

export default function ChatPage() {
  // Fill the whole screen under the top menu (edge to edge, cancelling the layout's padding).
  return (
    <div className="relative left-1/2 -my-8 h-[calc(100dvh-3.5rem)] w-screen -translate-x-1/2">
      <ChatApp />
    </div>
  );
}