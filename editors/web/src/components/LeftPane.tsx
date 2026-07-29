import {
  ChevronDown,
  History,
  Info,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  Plug,
  Plus,
  Sun,
  Trash2,
} from "lucide-react";
import type { AppInfo, Skill, ThreadSummary } from "../api/types";

type Props = {
  appInfo: AppInfo;
  currentThreadId: string;
  sessions: ThreadSummary[];
  skills: Skill[];
  showSkills: boolean;
  theme: "dark" | "light";
  onNewSession: () => void;
  onResumeThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  onShowThreadInfo: (threadId: string) => void;
  onToggleSkills: () => void;
  onToggleTheme: () => void;
  onToggleCollapsed: () => void;
  onOpenLatest: () => void;
  onOpenSettings: () => void;
};

export function LeftPane({
  appInfo,
  currentThreadId,
  sessions,
  skills,
  showSkills,
  theme,
  onNewSession,
  onResumeThread,
  onDeleteThread,
  onShowThreadInfo,
  onToggleSkills,
  onToggleTheme,
  onToggleCollapsed,
  onOpenLatest,
  onOpenSettings,
}: Props) {
  const initial = (appInfo.userName || "P").charAt(0).toUpperCase();
  return (
    <aside className="pane pane-left" data-left-pane>
      <div className="pane-expanded">
        <div className="pane-topbar">
          <button className="new-task-button" type="button" onClick={onNewSession}>
            新建任务
          </button>
        </div>
        <div className="pane-section-label">{showSkills ? "Skills" : "会话历史"}</div>
        <div className="session-list" hidden={showSkills}>
          {sessions.length === 0 ? (
            <div className="session-empty">
              <div className="session-empty-title">还没有历史会话</div>
              <div className="session-empty-copy">点击上方新建任务开始第一条对话。</div>
            </div>
          ) : (
            sessions.map((session) => {
              const current = session.id === currentThreadId;
              return (
                <div
                  className={`session-item${current ? " current" : ""}`}
                  key={session.id}
                  data-thread-id={session.id}
                >
                  <button
                    className="session-open"
                    type="button"
                    data-thread-open
                    data-thread-id={session.id}
                    onClick={() => onResumeThread(session.id)}
                  >
                    <span
                      className={`session-status${current ? " current" : ""}`}
                      title={`沙箱：${sessionSandboxLabel(session.sandboxBackend)}`}
                    >
                      {sessionIcon(session.sandboxBackend)}
                    </span>
                    <span className="session-main">
                      <span className="session-title">{session.title || "新建任务"}</span>
                      <span className="session-time">{session.relativeTime || "刚刚"}</span>
                    </span>
                  </button>
                  <div className="session-actions">
                    <button
                      className="session-action-button"
                      type="button"
                      title="删除会话"
                      aria-label="删除会话"
                      onClick={() => onDeleteThread(session.id)}
                    >
                      <Trash2 className="desktop-icon" aria-hidden="true" />
                    </button>
                    <button
                      className="session-action-button"
                      type="button"
                      title="查看会话信息"
                      aria-label="查看会话信息"
                      onClick={() => onShowThreadInfo(session.id)}
                    >
                      <Info className="desktop-icon" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
        <div className="skills-panel" hidden={!showSkills}>
          <div className="skills-list">
            {skills.length === 0 ? (
              <div className="session-empty">
                <div className="session-empty-title">暂无 Skills</div>
                <div className="session-empty-copy">在 ~/.pagent/skills/ 目录下放置技能即可。</div>
              </div>
            ) : (
              skills.map((skill) => (
                <div className="skill-item" key={skill.path || skill.name} title={skill.path}>
                  <span className="skill-name">{skill.name}</span>
                  <span className="skill-desc">{skill.description}</span>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="left-footer">
          <div className="user-menu">
            <button
              className="user-chip"
              type="button"
              aria-haspopup="menu"
              aria-expanded="false"
              title="账户与设置"
              onClick={onOpenSettings}
            >
              <span className="user-avatar">{initial}</span>
              <span className="user-name">{appInfo.userName || "pagent"}</span>
              <span className="user-chip-chevron" aria-hidden="true">
                <ChevronDown className="desktop-icon" />
              </span>
            </button>
          </div>
          <div className="left-footer-actions">
            <button className="icon-button" type="button" title="Skills" onClick={onToggleSkills}>
              <Plug className="desktop-icon" aria-hidden="true" />
            </button>
            <button className="icon-button active" type="button" title="钉住侧栏">
              <Pin className="desktop-icon" aria-hidden="true" />
            </button>
            <button className="icon-button" type="button" title="切换主题" onClick={onToggleTheme}>
              {theme === "light" ? (
                <Sun className="desktop-icon" aria-hidden="true" />
              ) : (
                <Moon className="desktop-icon" aria-hidden="true" />
              )}
            </button>
            <button
              className="icon-button"
              type="button"
              title="折叠左栏"
              onClick={onToggleCollapsed}
            >
              <PanelLeftClose className="desktop-icon" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
      <div className="pane-collapsed">
        <button className="collapsed-expand" type="button" title="展开左栏" onClick={onToggleCollapsed}>
          <PanelLeftOpen className="desktop-icon" aria-hidden="true" />
        </button>
        <button className="collapsed-icon" type="button" title="新建任务" onClick={onNewSession}>
          <Plus className="desktop-icon" aria-hidden="true" />
        </button>
        <button className="collapsed-icon" type="button" title="最近会话" onClick={onOpenLatest}>
          <History className="desktop-icon" aria-hidden="true" />
        </button>
        <div className="collapsed-bottom">
          <button className="collapsed-icon" type="button" title="切换主题" onClick={onToggleTheme}>
            {theme === "light" ? (
              <Sun className="desktop-icon" aria-hidden="true" />
            ) : (
              <Moon className="desktop-icon" aria-hidden="true" />
            )}
          </button>
          <button
            className="collapsed-icon user"
            type="button"
            title="账户与设置"
            aria-haspopup="menu"
            aria-expanded="false"
            onClick={onOpenSettings}
          >
            <span className="user-avatar small">{initial}</span>
          </button>
        </div>
      </div>
    </aside>
  );
}

function sessionSandboxLabel(backend: string): string {
  if (backend === "container" || backend === "docker" || backend === "podman") {
    return "container";
  }
  if (backend === "ssh") {
    return "ssh";
  }
  return "local";
}

function sessionIcon(backend: string) {
  if (backend === "ssh") {
    return <i className="codicon codicon-remote" aria-hidden="true" />;
  }
  if (backend === "container" || backend === "docker" || backend === "podman") {
    return <i className="codicon codicon-package" aria-hidden="true" />;
  }
  return <i className="codicon codicon-device-desktop" aria-hidden="true" />;
}
