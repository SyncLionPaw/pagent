import { Folder, HardDrive, Menu, PanelRight, Server } from "lucide-react";
import type { ContextUsageRing } from "@webview/context-usage";
import { ChatView } from "../chat/ChatView";
import type { RuntimeState, ThreadSummary, WireEvent } from "../api/types";
import { projectLabel } from "../lib/format";
import { Composer, type SlashCommand } from "./Composer";

type Props = {
  runtime: RuntimeState;
  sessions: ThreadSummary[];
  chatEvents: WireEvent[];
  historyEpoch: number;
  running: boolean;
  lastError: string;
  slashCommands: SlashCommand[];
  projectFiles: string[];
  sandboxFiles: string[];
  sidebarDocked: boolean;
  isMobile?: boolean;
  onOpenSessions?: () => void;
  onOpenWorkspace?: () => void;
  onPermit: (toolCallId: string, approved: boolean) => void;
  onSend: (text: string) => void;
  onCancel: () => void;
  onToggleYolo: () => void;
  onToggleSkills: () => void;
  onClearError: () => void;
  onOpenNewSession: () => void;
  onComposingChange: (composing: boolean) => void;
  onHistoryDock: () => void;
  onRingReady: (ring: ContextUsageRing | null) => void;
};

export function CenterPane({
  runtime,
  sessions,
  chatEvents,
  historyEpoch,
  running,
  lastError,
  slashCommands,
  projectFiles,
  sandboxFiles,
  sidebarDocked,
  isMobile = false,
  onOpenSessions,
  onOpenWorkspace,
  onPermit,
  onSend,
  onCancel,
  onToggleYolo,
  onToggleSkills,
  onClearError,
  onOpenNewSession,
  onComposingChange,
  onHistoryDock,
  onRingReady,
}: Props) {
  const title =
    sessions.find((session) => session.id === runtime.currentThreadId)?.title || "新建任务";
  const presence = sandboxPresenceClass(runtime);
  return (
    <section className="pane pane-center">
      <div className="pane-topbar center-topbar">
        {isMobile ? (
          <button
            className="mobile-nav-button"
            type="button"
            title="会话列表"
            aria-label="会话列表"
            onClick={onOpenSessions}
          >
            <Menu className="desktop-icon" aria-hidden="true" />
          </button>
        ) : null}
        <div className="center-title">{title}</div>
        <div className="center-header-side">
          {isMobile ? (
            <button
              className="mobile-nav-button"
              type="button"
              title="项目与沙箱"
              aria-label="项目与沙箱"
              onClick={onOpenWorkspace}
            >
              <PanelRight className="desktop-icon" aria-hidden="true" />
            </button>
          ) : (
            <>
              <button
                className="center-pill center-pill-button"
                type="button"
                title={runtime.projectPath}
                onClick={onOpenNewSession}
              >
                <span className="center-pill-icon" aria-hidden="true">
                  <Folder className="desktop-icon" />
                </span>
                <span>{projectLabel(runtime.projectPath)}</span>
              </button>
              <span className={`center-pill center-pill-status ${presence}`}>
                <span className="center-pill-icon" aria-hidden="true">
                  {runtime.sandboxBackend === "local" ? (
                    <HardDrive className="desktop-icon" />
                  ) : (
                    <Server className="desktop-icon" />
                  )}
                </span>
                <span>{sandboxBackendLabel(runtime)}</span>
              </span>
            </>
          )}
        </div>
      </div>
      <ChatView
        onPermit={onPermit}
        events={chatEvents}
        historyEpoch={historyEpoch}
        running={running}
      />
      <Composer
        running={running}
        yoloMode={runtime.yoloMode}
        lastError={lastError}
        slashCommands={slashCommands}
        projectFiles={projectFiles}
        sandboxFiles={sandboxFiles}
        sidebarDocked={sidebarDocked}
        onSend={onSend}
        onCancel={onCancel}
        onToggleYolo={onToggleYolo}
        onToggleSkills={onToggleSkills}
        onClearError={onClearError}
        onComposingChange={onComposingChange}
        onHistoryDock={onHistoryDock}
        onRingReady={onRingReady}
      />
    </section>
  );
}

function sandboxBackendLabel(runtime: RuntimeState): string {
  const backend = runtime.sandboxBackend;
  if (!backend) {
    return runtime.currentThreadId ? "待连接" : "未启动";
  }
  if (backend === "docker" || backend === "podman") {
    return "container";
  }
  return backend;
}

function sandboxPresenceClass(runtime: RuntimeState): "alive" | "dead" | "pending" {
  if (runtime.sandboxAlive === true) {
    return "alive";
  }
  if (runtime.sandboxAlive === false) {
    return "dead";
  }
  return "pending";
}
