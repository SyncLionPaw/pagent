import {
  ChevronDown,
  FileText,
  History,
  Info,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  PinOff,
  Plug,
  Plus,
  Settings,
  Sun,
  Trash2,
  Wrench,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AppInfo, Skill, ThreadSummary } from "../api/types";

type Props = {
  appInfo: AppInfo;
  currentThreadId: string;
  sessions: ThreadSummary[];
  skills: Skill[];
  showSkills: boolean;
  theme: "dark" | "light";
  sidebarPinned: boolean;
  onNewSession: () => void;
  onResumeThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  onShowThreadInfo: (threadId: string) => void;
  onToggleSkills: () => void;
  onToggleTheme: () => void;
  onToggleCollapsed: () => void;
  onTogglePin: () => void;
  onOpenLatest: () => void;
  onOpenSettings: () => void;
  onOpenDocsQr: () => void;
  onOpenOnboarding: () => void;
  onOpenDocs: () => void;
};

export function LeftPane({
  appInfo,
  currentThreadId,
  sessions,
  skills,
  showSkills,
  theme,
  sidebarPinned,
  onNewSession,
  onResumeThread,
  onDeleteThread,
  onShowThreadInfo,
  onToggleSkills,
  onToggleTheme,
  onToggleCollapsed,
  onTogglePin,
  onOpenLatest,
  onOpenSettings,
  onOpenDocsQr,
  onOpenOnboarding,
  onOpenDocs,
}: Props) {
  const initial = (appInfo.userName || "P").charAt(0).toUpperCase();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const onDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [menuOpen]);

  const runMenuAction = (action: () => void) => {
    setMenuOpen(false);
    action();
  };

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
          <div className={`user-menu${menuOpen ? " is-open" : ""}`} ref={menuRef}>
            <button
              className="user-chip"
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              title="账户与设置"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <span className="user-avatar">{initial}</span>
              <span className="user-name">{appInfo.userName || "pagent"}</span>
              <span className="user-chip-chevron" aria-hidden="true">
                <ChevronDown className="desktop-icon" />
              </span>
            </button>
            <div className="user-menu-dropdown" role="menu" hidden={!menuOpen}>
              <div className="user-menu-header">
                <span className="user-avatar">{initial}</span>
                <div className="user-menu-meta">
                  <div className="user-menu-name">{appInfo.userName || "pagent"}</div>
                  <div className="user-menu-status">未登录</div>
                </div>
              </div>
              <div className="user-menu-divider" />
              <button
                className="user-menu-item"
                type="button"
                role="menuitem"
                onClick={() => runMenuAction(onOpenDocsQr)}
              >
                <span className="user-menu-item-icon wechat">
                  <WechatIcon />
                </span>
                <span>扫码看文档</span>
              </button>
              <button
                className="user-menu-item"
                type="button"
                role="menuitem"
                onClick={() => runMenuAction(onOpenOnboarding)}
              >
                <span className="user-menu-item-icon">
                  <Wrench className="desktop-icon" />
                </span>
                <span>首次设置</span>
              </button>
              <button
                className="user-menu-item"
                type="button"
                role="menuitem"
                onClick={() => runMenuAction(onOpenSettings)}
              >
                <span className="user-menu-item-icon">
                  <Settings className="desktop-icon" />
                </span>
                <span>设置</span>
              </button>
              <button
                className="user-menu-item"
                type="button"
                role="menuitem"
                onClick={() => runMenuAction(onOpenDocs)}
              >
                <span className="user-menu-item-icon">
                  <FileText className="desktop-icon" />
                </span>
                <span>文档</span>
              </button>
            </div>
          </div>
          <div className="left-footer-actions">
            <button className="icon-button" type="button" title="Skills" onClick={onToggleSkills}>
              <Plug className="desktop-icon" aria-hidden="true" />
            </button>
            <button
              className={`icon-button${sidebarPinned ? " active" : ""}`}
              type="button"
              title={sidebarPinned ? "取消钉住" : "钉住侧栏"}
              onClick={onTogglePin}
            >
              {sidebarPinned ? (
                <Pin className="desktop-icon" aria-hidden="true" />
              ) : (
                <PinOff className="desktop-icon" aria-hidden="true" />
              )}
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
            aria-expanded={menuOpen}
            onClick={onToggleCollapsed}
          >
            <span className="user-avatar small">{initial}</span>
          </button>
        </div>
      </div>
    </aside>
  );
}

function WechatIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="desktop-icon"
      aria-hidden="true"
    >
      <path d="M11.176 14.429c-2.665 0-4.826-1.8-4.826-4.018 0-2.22 2.159-4.02 4.824-4.02S16 8.191 16 10.411c0 1.21-.65 2.301-1.666 3.036a.32.32 0 0 0-.12.366l.218.81a.6.6 0 0 1 .029.117.166.166 0 0 1-.162.162.2.2 0 0 1-.092-.03l-1.057-.61a.5.5 0 0 0-.256-.074.5.5 0 0 0-.142.021 5.7 5.7 0 0 1-1.576.22M9.064 9.542a.647.647 0 1 0 .557-1 .645.645 0 0 0-.646.647.6.6 0 0 0 .09.353Zm3.232.001a.646.646 0 1 0 .546-1 .645.645 0 0 0-.644.644.63.63 0 0 0 .098.356" />
      <path d="M0 6.826c0 1.455.781 2.765 2.001 3.656a.385.385 0 0 1 .143.439l-.161.6-.1.373a.5.5 0 0 0-.032.14.19.19 0 0 0 .193.193q.06 0 .111-.029l1.268-.733a.6.6 0 0 1 .308-.088q.088 0 .171.025a6.8 6.8 0 0 0 1.625.26 4.5 4.5 0 0 1-.177-1.251c0-2.936 2.785-5.02 5.824-5.02l.15.002C10.587 3.429 8.392 2 5.796 2 2.596 2 0 4.16 0 6.826m4.632-1.555a.77.77 0 1 1-1.54 0 .77.77 0 0 1 1.54 0m3.875 0a.77.77 0 1 1-1.54 0 .77.77 0 0 1 1.54 0" />
    </svg>
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
