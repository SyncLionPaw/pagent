import { useEffect, useRef } from "react";
import { ChatRenderer } from "@webview/render";
import type { WireEvent } from "../api/types";

type Props = {
  onPermit: (toolCallId: string, approved: boolean) => void;
  events: WireEvent[];
  historyEpoch: number;
  running: boolean;
};

/**
 * 复用 VS Code / Desktop 的 ChatRenderer（DOM 命令式），保证聊天区 100% 对标。
 */
export function ChatView({ onPermit, events, historyEpoch, running }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<ChatRenderer | undefined>(undefined);
  const seenRef = useRef(0);
  const permitRef = useRef(onPermit);
  permitRef.current = onPermit;

  useEffect(() => {
    if (!rootRef.current) {
      return;
    }
    const renderer = new ChatRenderer(rootRef.current, (id, approved) => {
      permitRef.current(id, approved);
    });
    rendererRef.current = renderer;
    seenRef.current = 0;
    return () => {
      renderer.clear();
      rendererRef.current = undefined;
    };
  }, [historyEpoch]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) {
      return;
    }
    for (let i = seenRef.current; i < events.length; i += 1) {
      const event = events[i];
      if (event.method === "LocalUserInput") {
        const text = event.params.text;
        if (typeof text === "string") {
          renderer.addUser(text);
        }
        continue;
      }
      if (event.method === "HistoryLoading") {
        renderer.showHistorySkeleton();
        continue;
      }
      renderer.handleEvent(event);
    }
    seenRef.current = events.length;
  }, [events]);

  useEffect(() => {
    // running 变化时无需额外处理；占位由 ChatRenderer 内部管理。
  }, [running]);

  return <div className="chat-log" ref={rootRef} data-chat-log />;
}
