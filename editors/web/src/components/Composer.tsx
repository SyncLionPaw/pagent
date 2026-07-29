import { ArrowUp, Folder, History, Package, Plug, Square, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ContextUsageRing } from "@webview/context-usage";

export type SlashCommand = {
  name: string;
  summary: string;
};

export type MentionSource = "project" | "sandbox";
export type MentionFile = {
  path: string;
  source: MentionSource;
};

type SlashItem = { kind: "slash"; command: SlashCommand };
type MentionItem = { kind: "mention"; file: MentionFile };
type PopupItem = SlashItem | MentionItem;

type Props = {
  running: boolean;
  yoloMode: boolean;
  lastError: string;
  slashCommands: SlashCommand[];
  projectFiles: string[];
  sandboxFiles: string[];
  sidebarDocked: boolean;
  onSend: (text: string) => void;
  onCancel: () => void;
  onToggleYolo: () => void;
  onToggleSkills: () => void;
  onClearError: () => void;
  onComposingChange: (composing: boolean) => void;
  onHistoryDock: () => void;
  onRingReady: (ring: ContextUsageRing | null) => void;
};

const INPUT_MAX_HEIGHT_PX = 160;
const MENTION_MATCH = /(?:^|\s)@([^\s@]*)$/;
const MENTION_LIMIT = 8;

export function Composer({
  running,
  yoloMode,
  lastError,
  slashCommands,
  projectFiles,
  sandboxFiles,
  sidebarDocked,
  onSend,
  onCancel,
  onToggleYolo,
  onToggleSkills,
  onClearError,
  onComposingChange,
  onHistoryDock,
  onRingReady,
}: Props) {
  const [text, setText] = useState("");
  const [items, setItems] = useState<PopupItem[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const ringMountRef = useRef<HTMLSpanElement>(null);
  const mentionRange = useRef<{ start: number; end: number }>({ start: 0, end: 0 });

  useEffect(() => {
    const mount = ringMountRef.current;
    if (!mount) {
      return;
    }
    const ring = new ContextUsageRing(mount);
    onRingReady(ring);
    return () => {
      onRingReady(null);
      mount.replaceChildren();
      document.querySelectorAll(".context-usage-popover").forEach((node) => node.remove());
    };
  }, [onRingReady]);

  useEffect(() => {
    const input = inputRef.current;
    if (!input) {
      return;
    }
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, INPUT_MAX_HEIGHT_PX)}px`;
  }, [text]);

  const closePopup = () => {
    setOpen(false);
    setItems([]);
  };

  const refreshPopup = (value: string, caret: number) => {
    const head = value.slice(0, caret);
    const match = MENTION_MATCH.exec(head);
    if (match) {
      const raw = match[1];
      mentionRange.current = { start: caret - raw.length - 1, end: caret };
      const { source, query } = parseMentionQuery(raw);
      const projectList = projectFiles.map<MentionFile>((path) => ({ path, source: "project" }));
      const sandboxList = sandboxFiles.map<MentionFile>((path) => ({ path, source: "sandbox" }));
      let picked: MentionFile[];
      if (source === "project") {
        picked = filterMentions(projectList, query);
      } else if (source === "sandbox") {
        picked = filterMentions(sandboxList, query);
      } else {
        const merged = mergeMentions(
          filterMentions(projectList, query),
          filterMentions(sandboxList, query),
        ).slice(0, MENTION_LIMIT);
        picked = [
          ...merged.filter((item) => item.source === "project"),
          ...merged.filter((item) => item.source === "sandbox"),
        ];
      }
      const next = picked.map<PopupItem>((file) => ({ kind: "mention", file }));
      setItems(next);
      setActive(0);
      setOpen(next.length > 0);
      return;
    }
    if (value.trimStart().startsWith("/") && !value.includes(" ")) {
      const query = value.trimStart().slice(1).toLowerCase();
      const matched = slashCommands.filter((command) =>
        command.name.toLowerCase().includes(query),
      );
      const next = matched.map<PopupItem>((command) => ({ kind: "slash", command }));
      setItems(next);
      setActive(0);
      setOpen(next.length > 0);
      return;
    }
    closePopup();
  };

  const applyItem = (item: PopupItem) => {
    const input = inputRef.current;
    if (item.kind === "slash") {
      const value = `/${item.command.name} `;
      setText(value);
      closePopup();
      window.requestAnimationFrame(() => input?.focus());
      return;
    }
    const value = text;
    const { start, end } = mentionRange.current;
    const before = value.slice(0, start);
    const after = value.slice(end);
    const insert = `@${mentionSourcePrefix(item.file.source)}:${item.file.path} `;
    const nextValue = `${before}${insert}${after}`;
    setText(nextValue);
    closePopup();
    window.requestAnimationFrame(() => {
      if (input) {
        const caret = before.length + insert.length;
        input.focus();
        input.setSelectionRange(caret, caret);
      }
    });
  };

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
    closePopup();
    onSend(value);
    setText("");
    onComposingChange(false);
    window.requestAnimationFrame(() => inputRef.current?.focus());
  };

  return (
    <div className="composer-dock">
      <div className="mention-popup" hidden={!open || items.length === 0}>
        {items.map((item, index) => (
          <PopupRow
            key={rowKey(item, index)}
            item={item}
            previous={items[index - 1]}
            active={index === active}
            onPick={() => applyItem(item)}
          />
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
            onComposingChange(value.trim().length > 0);
            const caret = event.target.selectionStart ?? value.length;
            refreshPopup(value, caret);
          }}
          onFocus={() => onComposingChange(true)}
          onBlur={() => {
            window.setTimeout(() => {
              closePopup();
              onComposingChange(text.trim().length > 0);
            }, 120);
          }}
          onKeyDown={(event) => {
            if (open && items.length > 0) {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActive((current) => (current + 1) % items.length);
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive((current) => (current - 1 + items.length) % items.length);
                return;
              }
              if (event.key === "Enter" || event.key === "Tab") {
                const item = items[active];
                if (item) {
                  event.preventDefault();
                  applyItem(item);
                  return;
                }
              }
              if (event.key === "Escape") {
                event.preventDefault();
                closePopup();
                return;
              }
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
              hidden={!sidebarDocked}
              title="展开会话列表"
              aria-label="展开会话列表"
              onMouseDown={(event) => event.preventDefault()}
              onClick={onHistoryDock}
            >
              <History className="desktop-icon" aria-hidden="true" />
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
            <span ref={ringMountRef} className="context-usage-mount" />
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

function PopupRow({
  item,
  previous,
  active,
  onPick,
}: {
  item: PopupItem;
  previous: PopupItem | undefined;
  active: boolean;
  onPick: () => void;
}) {
  const showDivider =
    item.kind === "mention" &&
    previous?.kind === "mention" &&
    previous.file.source !== item.file.source;
  return (
    <>
      {showDivider ? <div className="mention-divider" role="separator" /> : null}
      <button
        className={`mention-item${active ? " active" : ""}`}
        type="button"
        onMouseDown={(event) => event.preventDefault()}
        onClick={onPick}
      >
        {item.kind === "slash" ? (
          <>
            <span className="mention-icon" aria-hidden="true">
              /
            </span>
            <span className="mention-path">/{item.command.name}</span>
            <span className="mention-source mention-source-project">{item.command.summary}</span>
          </>
        ) : (
          <>
            <span className="mention-icon" aria-hidden="true">
              {item.file.source === "sandbox" ? (
                <Package className="desktop-icon" />
              ) : (
                <Folder className="desktop-icon" />
              )}
            </span>
            <span className="mention-path">{item.file.path}</span>
            <span className={`mention-source mention-source-${item.file.source}`}>
              {mentionSourceLabel(item.file.source)}
            </span>
          </>
        )}
      </button>
    </>
  );
}

function rowKey(item: PopupItem, index: number): string {
  return item.kind === "slash"
    ? `slash-${item.command.name}`
    : `mention-${item.file.source}-${item.file.path}-${index}`;
}

function mentionSourceLabel(source: MentionSource): string {
  return source === "project" ? "项目" : "沙箱";
}

function mentionSourcePrefix(source: MentionSource): string {
  return source === "sandbox" ? "sandbox" : "user";
}

function parseMentionQuery(raw: string): { source: MentionSource | null; query: string } {
  if (raw.startsWith("user:")) {
    return { source: "project", query: raw.slice(5) };
  }
  if (raw.startsWith("sandbox:")) {
    return { source: "sandbox", query: raw.slice(8) };
  }
  return { source: null, query: raw };
}

function scoreMention(pathText: string, query: string): number {
  if (!query) {
    return 1;
  }
  const lowerPath = pathText.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const index = lowerPath.indexOf(lowerQuery);
  if (index < 0) {
    return -1;
  }
  const base = lowerPath.slice(lowerPath.lastIndexOf("/") + 1);
  if (base.startsWith(lowerQuery)) {
    return 3;
  }
  if (index === 0) {
    return 2;
  }
  return 1;
}

function filterMentions(files: MentionFile[], query: string): MentionFile[] {
  const scored: Array<{ file: MentionFile; score: number }> = [];
  for (const file of files) {
    const score = scoreMention(file.path, query);
    if (score < 0) {
      continue;
    }
    scored.push({ file, score });
  }
  scored.sort((a, b) => {
    if (b.score !== a.score) {
      return b.score - a.score;
    }
    return a.file.path.length - b.file.path.length;
  });
  return scored.slice(0, MENTION_LIMIT).map((item) => item.file);
}

function mergeMentions(project: MentionFile[], sandbox: MentionFile[]): MentionFile[] {
  const merged: MentionFile[] = [];
  const max = Math.max(project.length, sandbox.length);
  for (let index = 0; index < max; index += 1) {
    if (index < project.length) {
      merged.push(project[index]);
    }
    if (index < sandbox.length) {
      merged.push(sandbox[index]);
    }
  }
  return merged;
}
