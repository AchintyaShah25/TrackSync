import type { Metadata } from "next";

import { ChatView } from "@/components/chat/ChatView";

export const metadata: Metadata = {
  title: "Ask about F1",
  description: "Ask about F1 rules, race history and stats, with cited sources.",
};

export default function ChatPage() {
  return (
    <div className="mx-auto w-full max-w-3xl">
      <ChatView />
    </div>
  );
}
