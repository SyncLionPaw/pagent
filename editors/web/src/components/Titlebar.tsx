import { Keyboard, Settings } from "lucide-react";
import { docsUrl } from "../lib/format";

type Props = {
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  onOpenShortcuts: () => void;
};

export function Titlebar({ theme, onToggleTheme, onOpenSettings, onOpenShortcuts }: Props) {
  const light = theme === "light";
  return (
    <div className="desktop-titlebar">
      <div className="titlebar-left">
        <button
          className="titlebar-switch"
          type="button"
          data-on={light}
          title="切换主题"
          aria-label="切换主题"
          aria-pressed={light}
          style={{ border: 0, background: "transparent", padding: 0 }}
          onClick={onToggleTheme}
        >
          <div className="titlebar-switch-track">
            <div
              className="titlebar-switch-thumb"
              style={{ transform: light ? "translateX(14px)" : "translateX(0)" }}
            />
          </div>
        </button>
      </div>
      <div className="titlebar-right">
        <a
          className="titlebar-action"
          href={docsUrl()}
          target="_blank"
          rel="noreferrer"
          title="打开文档"
          aria-label="打开文档"
        >
          <i className="codicon codicon-github" aria-hidden="true" />
        </a>
        <button
          className="titlebar-action"
          type="button"
          title="快捷键与心智模型"
          aria-label="快捷键与心智模型"
          onClick={onOpenShortcuts}
        >
          <Keyboard className="desktop-icon" size={16} strokeWidth={1.8} aria-hidden="true" />
        </button>
        <button
          className="titlebar-action title-settings-button"
          type="button"
          title="设置"
          aria-label="设置"
          onClick={onOpenSettings}
        >
          <Settings className="desktop-icon" size={16} strokeWidth={1.8} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
