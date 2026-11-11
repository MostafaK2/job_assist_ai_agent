"use client";

import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";

/** Renders the agent's replies as formatted text (bold, lists, links, code, tables). */
export default function MarkdownText() {
  return <MarkdownTextPrimitive remarkPlugins={[remarkGfm]} className="chat-markdown" />;
}