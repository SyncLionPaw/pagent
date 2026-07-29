import { Folder, HardDrive, Server } from "lucide-react";
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
  onPermit: (toolCallId: string, approved: boolean) => void;
  onSend: (text: string) => void;
  onCancel: () => void;
  onToggleYolo: () => void;
  onToggleSkills: () => void;
  onClearError: () => void;
  onOpenNewSession: () => void;
};

export function CenterPane({
  runtime,
  sessions,
  chatEvents,
  historyEpoch,
  running,
  lastError,
  slashCommands,
  onPermit,
  onSend,
  onCancel,
  onToggleYolo,
  onToggleSkills,
  onClearError,
  onOpenNewSession,
}: Props) {
  const title =
    sessions.find((session) => session.id === runtime.currentThreadId)?.title || "新建任务";
  const presence = sandboxPresenceClass(runtime);
  return (
    <section className="pane pane-center">
      <div className="pane-topbar center-topbar">
        <div className="center-title">{title}</div>
        <div className="center-header-side">
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
        onSend={onSend}
        onCancel={onCancel}
        onToggleYolo={onToggleYolo}
        onToggleSkills={onToggleSkills}
        onClearError={onClearError}
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
