import { ArrowUp, Plug, Square, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export type SlashCommand = {
  name: string;
  summary: string;
};

type Props = {
  running: boolean;
  yoloMode: boolean;
  lastError: string;
  slashCommands: SlashCommand[];
  onSend: (text: string) => void;
  onCancel: () => void;
  onToggleYolo: () => void;
  onToggleSkills: () => void;
  onClearError: () => void;
};

const INPUT_MAX_HEIGHT_PX = 160;

export function Composer({
  running,
  yoloMode,
  lastError,
  slashCommands,
  onSend,
  onCancel,
  onToggleYolo,
  onToggleSkills,
  onClearError,
}: Props) {
  const [text, setText] = useState("");
  const [slashOpen, setSlashOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const input = inputRef.current;
    if (!input) {
      return;
    }
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, INPUT_MAX_HEIGHT_PX)}px`;
  }, [text]);

  const canSend = text.trim().length > 0;
  const submit = () => {
    if (running) {
      onCancel();
      return;
    }
    const value = text.trim();
    if (!value) {
      return;
    }
    setSlashOpen(false);
    onSend(value);
    setText("");
    window.requestAnimationFrame(() => inputRef.current?.focus());
  };

  const applySlash = (name: string) => {
    setText(`/${name} `);
    setSlashOpen(false);
    window.requestAnimationFrame(() => inputRef.current?.focus());
  };

  return (
    <div className="composer-dock">
      <div className="mention-popup" hidden={!slashOpen || slashCommands.length === 0}>
        {slashCommands.map((command) => (
          <button
            className="mention-item"
            type="button"
            key={command.name}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => applySlash(command.name)}
          >
            <span className="mention-icon" aria-hidden="true">
              /
            </span>
            <span className="mention-path">/{command.name}</span>
            <span className="mention-source mention-source-project">{command.summary}</span>
          </button>
        ))}
      </div>
      <div className="composer composer-floating">
        <textarea
          id="prompt"
          ref={inputRef}
          value={text}
          placeholder="给 pagent 下达任务，输入 @ 引用文件"
          onChange={(event) => {
            const value = event.target.value;
            setText(value);
            setSlashOpen(value.trimStart().startsWith("/"));
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape" && slashOpen) {
              event.preventDefault();
              setSlashOpen(false);
              return;
            }
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <div className="composer-actions">
          <div className="composer-actions-start">
            <button
              type="button"
              className="composer-btn skills-button"
              title="Skills"
              aria-label="打开 Skills 面板"
              onClick={onToggleSkills}
            >
              <Plug className="desktop-icon" aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`composer-btn yolo-btn${yoloMode ? " active" : ""}`}
              title={
                yoloMode
                  ? "自动审批：开启（点击关闭 YOLO 模式）"
                  : "自动审批：关闭（点击开启 YOLO 模式）"
              }
              aria-label={yoloMode ? "YOLO 已开启" : "YOLO 模式"}
              onClick={onToggleYolo}
            >
              <Zap className="desktop-icon" aria-hidden="true" />
            </button>
            <button
              type="button"
              className="history-dock-dot"
              title="斜杠命令"
              aria-label="斜杠命令"
              onClick={() => setSlashOpen((open) => !open)}
            >
              /
            </button>
            <div
              className={`desktop-composer-hint${lastError ? " is-error" : ""}`}
              hidden={!lastError}
            >
              <span className="desktop-composer-hint-text">{lastError}</span>
              <button
                type="button"
                className="desktop-composer-hint-close"
                title="关闭"
                aria-label="关闭错误提示"
                onClick={onClearError}
              >
                x
              </button>
            </div>
          </div>
          <div className="composer-actions-end">
            <button
              className={`composer-btn primary${running ? " is-stop" : ""}`}
              type="button"
              title={running ? "停止" : "发送"}
              aria-label={running ? "停止" : "发送"}
              disabled={!running && !canSend}
              onClick={submit}
            >
              {running ? (
                <Square className="desktop-icon" aria-hidden="true" />
              ) : (
                <ArrowUp className="desktop-icon" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
