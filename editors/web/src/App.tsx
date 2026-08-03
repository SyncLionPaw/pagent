import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import type { ContextUsageRing } from "@webview/context-usage";
import type {
  AppInfo,
  AppSettings,
  ArtifactPreview,
  ArtifactSummary,
  EnvironmentCheck,
  NewSessionOptions,
  ResetSessionOptions,
  RuntimeState,
  SandboxStatus,
  SandboxTreeNode,
  Skill,
  ThreadMeta,
  ThreadSummary,
  WireEvent,
} from "./api/types";
import { createHostApi } from "./api/host";
import { HttpBridge, normalizeBaseUrl } from "./api/httpBridge";
import { CenterPane } from "./components/CenterPane";
import { ConfirmModal, type ConfirmOptions } from "./components/ConfirmModal";
import { DocsQrModal } from "./components/DocsQrModal";
import { LeftPane } from "./components/LeftPane";
import { NewSessionModal } from "./components/NewSessionModal";
import { Onboarding } from "./components/Onboarding";
import {
  RightPane,
  type ActivityState,
  type ProjectPane,
  type RightTab,
  type TerminalEntry,
} from "./components/RightPane";
import { SettingsModal, type ConfigSnapshot } from "./components/SettingsModal";
import { ShortcutsModal } from "./components/ShortcutsModal";
import { ThreadMetaModal } from "./components/ThreadMetaModal";
import { Titlebar } from "./components/Titlebar";
import type { SlashCommand } from "./components/Composer";
import { docsUrl, formatRelativeTime, parseThreadTimestamp, readStoredTheme } from "./lib/format";
import { MOBILE_MEDIA_QUERY, useMediaQuery, useMobileViewport } from "./lib/media";
import { mountToaster, toast } from "./lib/toast";

const SERVER_URL_KEY = "pagent-web-server-url";
const SERVER_TOKEN_KEY = "pagent-web-server-token";
const THEME_KEY = "pagent-web-theme";
const SIDEBAR_PINNED_KEY = "pagent-web-sidebar-pinned";
const LEFT_PANE_WIDTH_PX = 232;
const LEFT_COLLAPSED_WIDTH_PX = 44;
// 泊靠时保留的窄条宽度：不塌成 0，留一根可 hover / 点击唤回的 rail。
const LEFT_RAIL_WIDTH_PX = 10;
const RIGHT_PANE_WIDTH_PX = 352;
const RIGHT_COLLAPSED_WIDTH_PX = 44;
const LEFT_MIN_WIDTH_PX = 200;
const LEFT_MAX_WIDTH_PX = 320;
const RIGHT_MIN_WIDTH_PX = 300;
const RIGHT_MAX_WIDTH_PX = 420;

const CHAT_METHODS = new Set([
  "RunBegin",
  "ReasoningDelta",
  "TextDelta",
  "ToolCallBegin",
  "ToolResult",
  "PermitRequest",
  "SubagentEvent",
  "SlashResult",
  "HistoryReplay",
  "Error",
  "RunEnd",
]);

const defaultAppInfo: AppInfo = {
  name: "pagent",
  version: "",
  platform: "web",
  userName: "pagent",
};

const defaultRuntime: RuntimeState = {
  projectPath: "",
  activeHomePath: "",
  activeHomeScope: "user",
  currentThreadId: undefined,
  sandboxBackend: undefined,
  sandboxAlive: undefined,
  yoloMode: false,
  bridgeActive: false,
  transport: "http",
  status: "starting",
  lastError: undefined,
};

const defaultSandboxStatus: SandboxStatus = {
  threadId: "",
  backend: "",
  alive: false,
  workdir: "",
};

export default function App() {
  const [serverUrl, setServerUrl] = useState(
    () => window.localStorage.getItem(SERVER_URL_KEY) ?? "",
  );
  const [token, setToken] = useState(
    () => window.localStorage.getItem(SERVER_TOKEN_KEY) ?? "",
  );
  const [theme, setTheme] = useState<"dark" | "light">(() => readStoredTheme());
  const [connected, setConnected] = useState(false);
  const [appInfo, setAppInfo] = useState<AppInfo>(defaultAppInfo);
  const [runtime, setRuntime] = useState<RuntimeState>(defaultRuntime);
  const [sessions, setSessions] = useState<ThreadSummary[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [slashCommands, setSlashCommands] = useState<SlashCommand[]>([]);
  const [chatEvents, setChatEvents] = useState<WireEvent[]>([]);
  const [historyEpoch, setHistoryEpoch] = useState(0);
  const [running, setRunning] = useState(false);
  const [lastError, setLastError] = useState("");
  const [environment, setEnvironment] = useState<EnvironmentCheck>();
  const [configSnapshot, setConfigSnapshot] = useState<ConfigSnapshot>();
  const [settings, setSettings] = useState<AppSettings>();
  const [newSessionOptions, setNewSessionOptions] = useState<NewSessionOptions>();
  const [newSessionOpen, setNewSessionOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(true);
  const [leftWidth, setLeftWidth] = useState(LEFT_PANE_WIDTH_PX);
  const [rightWidth, setRightWidth] = useState(RIGHT_PANE_WIDTH_PX);
  const [sidebarPinned, setSidebarPinned] = useState(
    () => window.localStorage.getItem(SIDEBAR_PINNED_KEY) === "1",
  );
  const [sidebarDocked, setSidebarDocked] = useState(false);
  const [mobileDrawer, setMobileDrawer] = useState<"left" | "right" | null>(null);
  const isMobile = useMediaQuery(MOBILE_MEDIA_QUERY);
  useMobileViewport(isMobile);
  const [composing, setComposing] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [docsQrOpen, setDocsQrOpen] = useState(false);
  const [threadMetaOpen, setThreadMetaOpen] = useState(false);
  const [threadMeta, setThreadMeta] = useState<ThreadMeta>();
  const [threadMetaSession, setThreadMetaSession] = useState<ThreadSummary>();
  const [threadMetaError, setThreadMetaError] = useState("");
  const [confirm, setConfirm] = useState<{ options: ConfirmOptions; onConfirm: () => void }>();
  const [projectFiles, setProjectFiles] = useState<string[]>([]);
  const [showSkills, setShowSkills] = useState(false);
  const [activeTab, setActiveTab] = useState<RightTab>("project");
  const [projectPane, setProjectPane] = useState<ProjectPane>("files");
  const [projectTree, setProjectTree] = useState<SandboxTreeNode[]>([]);
  const [sandboxTree, setSandboxTree] = useState<SandboxTreeNode[]>([]);
  const [sandboxStatus, setSandboxStatus] = useState<SandboxStatus>(defaultSandboxStatus);
  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [artifactPreview, setArtifactPreview] = useState<ArtifactPreview>();
  const [terminalEntries, setTerminalEntries] = useState<TerminalEntry[]>([]);

  const baseUrl = useMemo(() => normalizeBaseUrl(serverUrl), [serverUrl]);
  const hostApi = useMemo(
    () => createHostApi(baseUrl, token.trim() || undefined),
    [baseUrl, token],
  );
  const bridgeRef = useRef<HttpBridge | undefined>(undefined);
  const initializedRef = useRef(false);
  const runtimeRef = useRef(runtime);
  const yoloRef = useRef(runtime.yoloMode);
  const handleWireEventRef = useRef<(event: WireEvent) => void>(() => undefined);
  const ringRef = useRef<ContextUsageRing | null>(null);
  const keepSidebarOpenRef = useRef(false);

  const sandboxFiles = useMemo(() => flattenSandboxTree(sandboxTree), [sandboxTree]);
  const activityState: ActivityState = lastError ? "error" : running ? "running" : "sleeping";

  useEffect(() => {
    runtimeRef.current = runtime;
    yoloRef.current = runtime.yoloMode;
  }, [runtime]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    mountToaster();
  }, []);

  const refreshProjectFiles = useCallback(() => {
    void hostApi
      .listProjectFiles(runtimeRef.current.projectPath)
      .then((files) => setProjectFiles(Array.isArray(files) ? files : []))
      .catch(() => setProjectFiles([]));
  }, [hostApi]);

  const appendTerminal = useCallback((kind: TerminalEntry["kind"], text: string) => {
    const compact = summarize(text, 220);
    if (!compact) {
      return;
    }
    setTerminalEntries((entries) => [...entries.slice(-47), { kind, text: compact }]);
  }, []);

  const sendCommand = useCallback((command: Record<string, unknown>) => {
    bridgeRef.current?.send(command);
  }, []);

  const withProject = useCallback((command: Record<string, unknown>) => {
    const projectPath = runtimeRef.current.projectPath;
    return projectPath ? { ...command, project_path: projectPath } : command;
  }, []);

  const refreshRuntime = useCallback(() => {
    void hostApi
      .getRuntimeState()
      .then((state) => {
        setRuntime((current) => ({
          ...current,
          ...state,
          yoloMode: state.yoloMode,
          status: state.status || current.status,
        }));
      })
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  }, [hostApi]);

  const refreshProjectTree = useCallback(() => {
    void hostApi
      .listProjectTree(runtimeRef.current.projectPath)
      .then((nodes) => setProjectTree(coerceTreeNodes(nodes)))
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  }, [hostApi]);

  const refreshArtifacts = useCallback(() => {
    void hostApi
      .listArtifacts(runtimeRef.current.projectPath)
      .then(setArtifacts)
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  }, [hostApi]);

  const refreshSettings = useCallback(() => {
    void hostApi
      .getSettings()
      .then(setSettings)
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  }, [hostApi]);

  const refreshNewSessionOptions = useCallback(() => {
    setNewSessionOptions(undefined);
    void hostApi
      .getNewSessionOptions(runtimeRef.current.projectPath)
      .then(setNewSessionOptions)
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  }, [hostApi]);

  const refreshSandbox = useCallback(() => {
    sendCommand(withProject({ cmd: "sandbox_status" }));
    sendCommand(withProject({ cmd: "sandbox_tree" }));
  }, [sendCommand, withProject]);

  const refreshEnvironment = useCallback(() => {
    sendCommand({ cmd: "environment_check", include_disk: true });
  }, [sendCommand]);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([hostApi.getAppInfo(), hostApi.getRuntimeState()])
      .then(([info, state]) => {
        if (cancelled) {
          return;
        }
        setAppInfo(info);
        setRuntime((current) => ({ ...current, ...state }));
      })
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
    refreshSettings();
    refreshProjectTree();
    refreshArtifacts();
    return () => {
      cancelled = true;
    };
  }, [hostApi, refreshArtifacts, refreshProjectTree, refreshSettings]);

  useEffect(() => {
    initializedRef.current = false;
    setConnected(false);
    const bridge = new HttpBridge(baseUrl, token.trim() || undefined, {
      onEvent(event) {
        handleWireEventRef.current(event);
        if (!initializedRef.current) {
          initializedRef.current = true;
          setConnected(true);
          bridge.send({ cmd: "client_features", features: { subagent_events: true } });
          bridge.send({ cmd: "commands" });
          bridge.send(withProject({ cmd: "list_threads" }));
          bridge.send({ cmd: "environment_check" });
          bridge.send({ cmd: "get_config" });
        }
      },
      onError(error) {
        setConnected(false);
        setLastError(error.message);
        appendTerminal("stderr", error.message);
      },
      onClose() {
        setConnected(false);
        setLastError("事件流已断开");
        appendTerminal("stderr", "事件流已断开");
      },
    });
    bridgeRef.current = bridge;
    bridge.start();
    return () => {
      bridge.stop();
      if (bridgeRef.current === bridge) {
        bridgeRef.current = undefined;
      }
    };
  }, [appendTerminal, baseUrl, token, withProject]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      sendCommand(withProject({ cmd: "sandbox_status" }));
      if (activeTab === "sandbox") {
        sendCommand(withProject({ cmd: "sandbox_tree" }));
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeTab, sendCommand, withProject]);

  useEffect(() => {
    refreshProjectTree();
    refreshArtifacts();
    refreshProjectFiles();
  }, [runtime.projectPath, refreshArtifacts, refreshProjectTree, refreshProjectFiles]);

  const providerConfigured =
    configSnapshot?.provider?.api_key_configured === true ||
    environment?.apiKeyConfigured === true;
  const providerKnownMissing =
    configSnapshot?.provider?.api_key_configured === false ||
    environment?.apiKeyConfigured === false;

  useEffect(() => {
    if (providerConfigured) {
      setOnboardingOpen(false);
      return;
    }
    if (providerKnownMissing) {
      setOnboardingOpen(true);
    }
  }, [providerConfigured, providerKnownMissing]);

  const setupBlocked = providerKnownMissing && !providerConfigured;

  useEffect(() => {
    if (!isMobile) {
      return;
    }
    setMobileDrawer(null);
    setSidebarDocked(false);
  }, [isMobile]);

  // 自动泊靠：对标 desktop syncComposerDock。未钉住时，聚焦/有草稿/运行中则收起左栏。
  useEffect(() => {
    if (isMobile) {
      return;
    }
    if (sidebarPinned) {
      keepSidebarOpenRef.current = false;
      setSidebarDocked(false);
      return;
    }
    const active = composing || running;
    if (keepSidebarOpenRef.current) {
      if (!active) {
        keepSidebarOpenRef.current = false;
      } else {
        setSidebarDocked(false);
        return;
      }
    }
    setSidebarDocked(active);
  }, [composing, running, sidebarPinned, isMobile]);

  const togglePin = useCallback(() => {
    setSidebarPinned((prev) => {
      const next = !prev;
      window.localStorage.setItem(SIDEBAR_PINNED_KEY, next ? "1" : "0");
      if (next) {
        keepSidebarOpenRef.current = false;
        setSidebarDocked(false);
      }
      return next;
    });
  }, []);

  const undockSidebar = useCallback(() => {
    keepSidebarOpenRef.current = true;
    setSidebarDocked(false);
    setLeftCollapsed(false);
  }, []);

  const openMobileDrawer = useCallback((side: "left" | "right") => {
    setMobileDrawer(side);
    if (side === "left") {
      keepSidebarOpenRef.current = true;
      setSidebarDocked(false);
      setLeftCollapsed(false);
    } else {
      setRightCollapsed(false);
    }
  }, []);

  const closeMobileDrawer = useCallback(() => {
    setMobileDrawer(null);
  }, []);

  const openSessions = useCallback(() => {
    if (isMobile) {
      openMobileDrawer("left");
      return;
    }
    undockSidebar();
  }, [isMobile, openMobileDrawer, undockSidebar]);

  const handleRingReady = useCallback((ring: ContextUsageRing | null) => {
    ringRef.current = ring;
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (mobileDrawer) {
          setMobileDrawer(null);
          return;
        }
        if (confirm) {
          setConfirm(undefined);
          return;
        }
        if (newSessionOpen) {
          setNewSessionOpen(false);
          return;
        }
        if (threadMetaOpen) {
          setThreadMetaOpen(false);
          return;
        }
        if (settingsOpen) {
          setSettingsOpen(false);
          return;
        }
        if (docsQrOpen) {
          setDocsQrOpen(false);
          return;
        }
        if (shortcutsOpen) {
          setShortcutsOpen(false);
          return;
        }
        if (artifactPreview) {
          setArtifactPreview(undefined);
          return;
        }
        return;
      }
      if (!event.metaKey && !event.ctrlKey) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "l") {
        event.preventDefault();
        setLeftCollapsed((collapsed) => !collapsed);
        keepSidebarOpenRef.current = false;
        setSidebarDocked(false);
      } else if (key === "r") {
        event.preventDefault();
        setRightCollapsed((collapsed) => !collapsed);
      } else if (key === "k") {
        event.preventDefault();
        setShortcutsOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    confirm,
    newSessionOpen,
    threadMetaOpen,
    settingsOpen,
    docsQrOpen,
    shortcutsOpen,
    artifactPreview,
    mobileDrawer,
  ]);

  const handleWireEvent = (event: WireEvent) => {
    ringRef.current?.handleWireEvent(event);
    if (CHAT_METHODS.has(event.method)) {
      if (event.method === "HistoryReplay") {
        setChatEvents([event]);
        setHistoryEpoch((epoch) => epoch + 1);
      } else {
        setChatEvents((events) => [...events, event]);
      }
    }

    if (event.method === "SlashCommands") {
      setSlashCommands(readSlashCommands(event.params.commands));
      return;
    }
    if (event.method === "ThreadList") {
      setSessions(readThreadSummaries(event.params.threads));
      return;
    }
    if (event.method === "Skills") {
      setSkills(readSkills(event.params.skills));
      return;
    }
    if (event.method === "SandboxTree") {
      const threadId = readString(event.params, "thread_id");
      const workdir = readString(event.params, "workdir");
      setSandboxTree(coerceTreeNodes(event.params.nodes));
      setSandboxStatus((current) => ({
        ...current,
        threadId: threadId || current.threadId,
        workdir: workdir || current.workdir,
      }));
      return;
    }
    if (event.method === "SandboxStatus") {
      const status = readSandboxStatus(event.params);
      setSandboxStatus(status);
      setRuntime((current) => ({
        ...current,
        currentThreadId: status.threadId || current.currentThreadId,
        sandboxBackend: status.backend || current.sandboxBackend,
        sandboxAlive: status.threadId || current.currentThreadId ? status.alive : current.sandboxAlive,
      }));
      return;
    }
    if (event.method === "ConfigSnapshot") {
      setConfigSnapshot(event.params as ConfigSnapshot);
      return;
    }
    if (event.method === "EnvironmentCheck") {
      setEnvironment(readEnvironmentCheck(event.params));
      return;
    }
    if (event.method === "CurrentThread") {
      const threadId = readString(event.params, "thread_id");
      const projectPath = readString(event.params, "project_path");
      setRuntime((current) => ({
        ...current,
        currentThreadId: threadId || current.currentThreadId,
        projectPath: projectPath || current.projectPath,
      }));
      return;
    }

    if (event.method === "RunBegin") {
      setRunning(true);
      setLastError("");
      appendTerminal("status", `开始：${String(event.params.user_input ?? "")}`);
      return;
    }
    if (event.method === "RunEnd") {
      setRunning(false);
      appendTerminal("status", "任务已结束，等待下一条指令。");
      sendCommand(withProject({ cmd: "list_threads" }));
      refreshRuntime();
      refreshArtifacts();
      refreshSandbox();
      return;
    }
    if (event.method === "Error") {
      setRunning(false);
      const message = readString(event.params, "message") || "未知错误";
      setLastError(message);
      appendTerminal("stderr", message);
      sendCommand(withProject({ cmd: "list_threads" }));
      return;
    }
    if (event.method === "HistoryReplay") {
      setRunning(false);
      const threadId = readString(event.params, "thread_id");
      const projectPath = readString(event.params, "project_path");
      setRuntime((current) => ({
        ...current,
        currentThreadId: threadId || undefined,
        projectPath: projectPath || current.projectPath,
        sandboxAlive: threadId ? current.sandboxAlive : undefined,
      }));
      setLastError("");
      sendCommand(withProject({ cmd: "list_threads" }));
      refreshRuntime();
      refreshArtifacts();
      refreshSandbox();
      return;
    }
    if (event.method === "PermitRequest") {
      const toolCallId = readString(event.params, "tool_call_id");
      if (toolCallId && yoloRef.current) {
        sendCommand({ cmd: "permit", tool_call_id: toolCallId });
      }
      return;
    }
    if (event.method === "ToolCallBegin") {
      appendTerminal(
        "command",
        buildToolPreview(readString(event.params, "name"), readString(event.params, "arguments")),
      );
      return;
    }
    if (event.method === "ToolResult") {
      appendTerminal("stdout", String(event.params.content ?? ""));
      return;
    }
    const subagent = unwrapSubagentEvent(event);
    if (subagent) {
      appendTerminal("status", `[subagent:${subagent.name || "subagent"}] ${subagent.inner.method}`);
    }
  };
  handleWireEventRef.current = handleWireEvent;

  const sendUser = (text: string) => {
    if (!text.trim()) {
      return;
    }
    if (!text.trimStart().startsWith("/")) {
      setChatEvents((events) => [
        ...events,
        { method: "LocalUserInput", params: { text } },
      ]);
      setRunning(true);
    }
    setLastError("");
    appendTerminal("command", text);
    sendCommand(withProject({ cmd: "user", text }));
  };

  const cancel = () => {
    appendTerminal("status", "请求停止当前任务…");
    sendCommand({ cmd: "cancel" });
  };

  const resetSession = (options?: ResetSessionOptions) => {
    setNewSessionOpen(false);
    setChatEvents((events) => [...events, { method: "HistoryLoading", params: {} }]);
    setRunning(false);
    if (options?.projectPath) {
      setRuntime((current) => ({
        ...current,
        projectPath: options.projectPath ?? current.projectPath,
        sandboxBackend: options.backend ?? current.sandboxBackend,
        sandboxAlive: undefined,
      }));
    }
    sendCommand({ cmd: "reset", ...commandOptions(options) });
  };

  const resumeThread = (threadId: string) => {
    const session = sessions.find((item) => item.id === threadId);
    setChatEvents((events) => [...events, { method: "HistoryLoading", params: {} }]);
    setRunning(false);
    sendCommand({
      cmd: "resume",
      thread_id: threadId,
      project_path: session?.projectPath || runtimeRef.current.projectPath,
    });
    if (isMobile) {
      setMobileDrawer(null);
    }
  };

  const deleteThread = (threadId: string) => {
    setConfirm({
      options: {
        title: "删除会话",
        message: "确定删除这个会话吗？此操作不可撤销。",
        confirmText: "删除",
        cancelText: "取消",
        tone: "danger",
      },
      onConfirm: () => {
        setConfirm(undefined);
        if (threadId === runtimeRef.current.currentThreadId) {
          setChatEvents((events) => [...events, { method: "HistoryLoading", params: {} }]);
        }
        sendCommand(withProject({ cmd: "delete_thread", thread_id: threadId }));
      },
    });
  };

  const toggleYolo = () => {
    const next = !runtimeRef.current.yoloMode;
    setRuntime((current) => ({ ...current, yoloMode: next }));
    void hostApi
      .setYoloMode(next)
      .then((result) => {
        setRuntime((current) => ({ ...current, yoloMode: result.yoloMode }));
        appendTerminal("status", result.yoloMode ? "YOLO 已开启" : "YOLO 已关闭");
        if (result.yoloMode) {
          toast("YOLO 已开启", { description: "工具调用将自动审批", type: "warning" });
        } else {
          toast("YOLO 已关闭", { description: "工具调用将逐个确认", type: "success" });
        }
      })
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  };

  const openNewSession = () => {
    setNewSessionOpen(true);
    refreshNewSessionOptions();
  };

  const openSettings = () => {
    setSettingsOpen(true);
    refreshSettings();
    refreshEnvironment();
    sendCommand({ cmd: "get_config" });
  };

  const saveConnection = (nextUrl: string, nextToken: string) => {
    window.localStorage.setItem(SERVER_URL_KEY, nextUrl);
    window.localStorage.setItem(SERVER_TOKEN_KEY, nextToken);
    setServerUrl(nextUrl);
    setToken(nextToken);
  };

  const showThreadInfo = (threadId: string) => {
    setThreadMeta(undefined);
    setThreadMetaError("");
    setThreadMetaSession(sessions.find((item) => item.id === threadId));
    setThreadMetaOpen(true);
    void hostApi
      .getThreadMeta(threadId)
      .then((meta: ThreadMeta) => setThreadMeta(meta))
      .catch((error: unknown) => setThreadMetaError(toErrorMessage(error)));
  };

  const openOnboarding = () => {
    refreshEnvironment();
    sendCommand({ cmd: "get_config" });
    setOnboardingOpen(true);
  };

  const previewArtifact = (path: string) => {
    setArtifactPreview(undefined);
    void hostApi
      .readArtifact(path, runtimeRef.current.projectPath)
      .then(setArtifactPreview)
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  };

  const openArtifact = (path: string) => {
    void hostApi
      .openArtifact(path, runtimeRef.current.projectPath)
      .catch((error: unknown) => setLastError(toErrorMessage(error)));
  };

  const leftHidden = !isMobile && sidebarDocked;
  const workbenchStyle = isMobile
    ? undefined
    : ({
      "--left-pane-width": leftHidden
        ? `${LEFT_RAIL_WIDTH_PX}px`
        : `${leftCollapsed ? LEFT_COLLAPSED_WIDTH_PX : leftWidth}px`,
      "--right-pane-width": `${rightCollapsed ? RIGHT_COLLAPSED_WIDTH_PX : rightWidth}px`,
      "--left-gap": leftHidden || leftCollapsed ? "0px" : "8px",
      "--right-gap": rightCollapsed ? "0px" : "8px",
    } as CSSProperties);

  const startResize = (side: "left" | "right") => (event: ReactPointerEvent<HTMLDivElement>) => {
    if (isMobile) {
      return;
    }
    if ((side === "left" && leftCollapsed) || (side === "right" && rightCollapsed)) {
      return;
    }
    const handle = event.currentTarget;
    const startX = event.clientX;
    const startWidth = side === "left" ? leftWidth : rightWidth;
    handle.setPointerCapture(event.pointerId);
    const onMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientX - startX;
      if (side === "left") {
        setLeftWidth(Math.max(LEFT_MIN_WIDTH_PX, Math.min(LEFT_MAX_WIDTH_PX, startWidth + delta)));
      } else {
        setRightWidth(
          Math.max(RIGHT_MIN_WIDTH_PX, Math.min(RIGHT_MAX_WIDTH_PX, startWidth - delta)),
        );
      }
    };
    const onUp = () => {
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
      handle.removeEventListener("pointercancel", onUp);
    };
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
    handle.addEventListener("pointercancel", onUp);
  };

  const toggleTheme = () => setTheme((current) => (current === "dark" ? "light" : "dark"));

  return (
    <div id="app">
      <div className="desktop-root">
        <div
          className={`desktop-shell macos${setupBlocked ? " is-setup-blocked" : ""}${isMobile ? " is-mobile" : ""}`}
          data-shell
        >
          <Titlebar
            theme={theme}
            onToggleTheme={toggleTheme}
            onOpenSettings={openSettings}
            onOpenShortcuts={() => setShortcutsOpen(true)}
          />
          {isMobile && mobileDrawer ? (
            <button
              className="mobile-drawer-backdrop"
              type="button"
              aria-label="关闭侧栏"
              onClick={closeMobileDrawer}
            />
          ) : null}
          <div
            className="desktop-workbench"
            data-workbench
            data-left-collapsed={isMobile ? true : leftCollapsed}
            data-right-collapsed={isMobile ? true : rightCollapsed}
            data-sidebar-docked={leftHidden}
            data-mobile={isMobile ? "true" : "false"}
            data-mobile-drawer={mobileDrawer ?? "none"}
            style={workbenchStyle}
          >
            <LeftPane
              appInfo={appInfo}
              currentThreadId={runtime.currentThreadId ?? ""}
              sessions={sessions}
              skills={skills}
              showSkills={showSkills}
              theme={theme}
              sidebarPinned={sidebarPinned}
              onNewSession={openNewSession}
              onResumeThread={resumeThread}
              onDeleteThread={deleteThread}
              onShowThreadInfo={showThreadInfo}
              onToggleSkills={() => {
                setShowSkills((open) => !open);
                sendCommand({ cmd: "skills" });
                setLeftCollapsed(false);
              }}
              onToggleTheme={toggleTheme}
              onToggleCollapsed={() => setLeftCollapsed((collapsed) => !collapsed)}
              onTogglePin={togglePin}
              onUndock={undockSidebar}
              onOpenLatest={() => {
                const latest = sessions[0];
                if (latest) {
                  resumeThread(latest.id);
                }
              }}
              onOpenSettings={openSettings}
              onOpenDocsQr={() => setDocsQrOpen(true)}
              onOpenOnboarding={openOnboarding}
              onOpenDocs={() => window.open(docsUrl(), "_blank", "noreferrer")}
            />
            <div className="pane-resizer" data-resizer="left" onPointerDown={startResize("left")} />
            <CenterPane
              runtime={{
                ...runtime,
                bridgeActive: connected,
                lastError,
              }}
              sessions={sessions}
              chatEvents={chatEvents}
              historyEpoch={historyEpoch}
              running={running}
              lastError={lastError}
              slashCommands={slashCommands}
              projectFiles={projectFiles}
              sandboxFiles={sandboxFiles}
              isMobile={isMobile}
              sidebarDocked={isMobile ? mobileDrawer !== "left" : sidebarDocked}
              onOpenSessions={() => openMobileDrawer("left")}
              onOpenWorkspace={() => openMobileDrawer("right")}
              onPermit={(toolCallId, approved) =>
                sendCommand(
                  approved
                    ? { cmd: "permit", tool_call_id: toolCallId }
                    : { cmd: "deny", tool_call_id: toolCallId },
                )
              }
              onSend={sendUser}
              onCancel={cancel}
              onToggleYolo={toggleYolo}
              onToggleSkills={() => {
                setShowSkills((open) => !open);
                sendCommand({ cmd: "skills" });
                setLeftCollapsed(false);
              }}
              onClearError={() => setLastError("")}
              onOpenNewSession={openNewSession}
              onComposingChange={setComposing}
              onHistoryDock={openSessions}
              onRingReady={handleRingReady}
            />
            <div className="pane-resizer" data-resizer="right" onPointerDown={startResize("right")} />
            <RightPane
              activeTab={activeTab}
              projectPane={projectPane}
              runtime={runtime}
              projectTree={projectTree}
              sandboxTree={sandboxTree}
              sandboxStatus={sandboxStatus}
              artifacts={artifacts}
              artifactPreview={artifactPreview}
              terminalEntries={terminalEntries}
              activityState={activityState}
              onTabChange={(tab) => {
                setActiveTab(tab);
                if (tab === "sandbox") {
                  refreshSandbox();
                }
                if (tab === "project") {
                  refreshProjectTree();
                  refreshArtifacts();
                }
              }}
              onProjectPaneChange={(pane) => {
                setProjectPane(pane);
                if (pane === "artifacts") {
                  refreshArtifacts();
                }
              }}
              onToggleCollapsed={() => setRightCollapsed((collapsed) => !collapsed)}
              onRefreshProject={() => {
                if (projectPane === "artifacts") {
                  refreshArtifacts();
                } else {
                  refreshProjectTree();
                }
              }}
              onRefreshSandbox={refreshSandbox}
              onOpenArtifact={openArtifact}
              onPreviewArtifact={previewArtifact}
              onCloseArtifactPreview={() => setArtifactPreview(undefined)}
            />
          </div>
        </div>

        <NewSessionModal
          open={newSessionOpen}
          options={newSessionOptions}
          projectPath={runtime.projectPath}
          onClose={() => setNewSessionOpen(false)}
          onSubmit={resetSession}
        />
        <SettingsModal
          open={settingsOpen}
          settings={settings}
          environment={environment}
          config={configSnapshot}
          serverUrl={serverUrl}
          token={token}
          onClose={() => setSettingsOpen(false)}
          onSaveConnection={saveConnection}
          onRefreshEnvironment={refreshEnvironment}
        />
        <Onboarding
          open={onboardingOpen}
          blocked={providerKnownMissing && !providerConfigured}
          environment={environment}
          config={configSnapshot}
          onClose={() => {
            if (!providerKnownMissing) {
              setOnboardingOpen(false);
            }
          }}
          onSubmit={(setup) => {
            sendCommand({
              cmd: "set_provider",
              api_key: setup.apiKey,
              model: setup.model,
              base_url: setup.baseUrl,
            });
            sendCommand({ cmd: "environment_check" });
          }}
        />
        <ThreadMetaModal
          open={threadMetaOpen}
          meta={threadMeta}
          session={threadMetaSession}
          error={threadMetaError}
          onClose={() => setThreadMetaOpen(false)}
        />
        <ShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
        <DocsQrModal open={docsQrOpen} onClose={() => setDocsQrOpen(false)} />
        <ConfirmModal
          open={Boolean(confirm)}
          options={confirm?.options ?? { title: "", message: "" }}
          onCancel={() => setConfirm(undefined)}
          onConfirm={() => confirm?.onConfirm()}
        />
      </div>
    </div>
  );
}

/** 把沙箱目录树拍平成相对路径清单，供 @ 引用补全。 */
function flattenSandboxTree(nodes: SandboxTreeNode[]): string[] {
  const paths: string[] = [];
  const walk = (list: SandboxTreeNode[]): void => {
    for (const node of list) {
      if (node.kind === "file") {
        paths.push(node.id);
      } else if (node.children) {
        walk(node.children);
      }
    }
  };
  walk(nodes);
  return paths;
}

function readString(params: Record<string, unknown>, key: string): string {
  const value = params[key];
  return typeof value === "string" ? value : "";
}

function readBoolean(params: Record<string, unknown>, camelKey: string, snakeKey: string): boolean {
  const value = params[camelKey] ?? params[snakeKey];
  return value === true;
}

function readNumber(params: Record<string, unknown>, camelKey: string, snakeKey: string): number | undefined {
  const value = params[camelKey] ?? params[snakeKey];
  return typeof value === "number" ? value : undefined;
}

function readEnvironmentCheck(params: Record<string, unknown>): EnvironmentCheck {
  const runtime = params.containerRuntime ?? params.container_runtime;
  return {
    uvInstalled: readBoolean(params, "uvInstalled", "uv_installed"),
    uvPath: readString(params, "uvPath") || readString(params, "uv_path"),
    pagentInstalled: readBoolean(params, "pagentInstalled", "pagent_installed"),
    pagentPath: readString(params, "pagentPath") || readString(params, "pagent_path"),
    apiKeyConfigured: readBoolean(params, "apiKeyConfigured", "api_key_configured"),
    dockerInstalled: readBoolean(params, "dockerInstalled", "docker_installed"),
    podmanInstalled: readBoolean(params, "podmanInstalled", "podman_installed"),
    containerRuntime: runtime === "docker" || runtime === "podman" ? runtime : undefined,
    sandboxImage: readString(params, "sandboxImage") || readString(params, "sandbox_image"),
    sandboxImageExists: readBoolean(params, "sandboxImageExists", "sandbox_image_exists"),
    configPath: readString(params, "configPath") || readString(params, "config_path"),
    dataHomePath: readString(params, "dataHomePath") || readString(params, "data_home_path"),
    dataHomeLabel: readString(params, "dataHomeLabel") || readString(params, "data_home_label"),
    dataHomeBytes: readNumber(params, "dataHomeBytes", "data_home_bytes"),
    sandboxImageBytes: readNumber(params, "sandboxImageBytes", "sandbox_image_bytes"),
  };
}

function readSandboxStatus(params: Record<string, unknown>): SandboxStatus {
  return {
    threadId: readString(params, "thread_id") || readString(params, "threadId"),
    backend: readString(params, "backend"),
    alive: params.alive === true,
    workdir: readString(params, "workdir"),
  };
}

function readThreadSummaries(raw: unknown): ThreadSummary[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (typeof item !== "object" || item === null) {
      return [];
    }
    const record = item as Record<string, unknown>;
    const id = readString(record, "id");
    if (!id) {
      return [];
    }
    // cloud 后端带 ISO 时间戳；desktop 只有 thread-YYYYMMDD-HHMMSS 格式的 id。
    const isoTime =
      readString(record, "last_message_at") ||
      readString(record, "created_at");
    const time = isoTime ? new Date(isoTime) : parseThreadTimestamp(id);
    return [
      {
        id,
        title: readString(record, "title") || "新建任务",
        relativeTime: formatRelativeTime(time),
        projectPath: readString(record, "project_path") || readString(record, "projectPath"),
        sandboxBackend: readString(record, "backend") || readString(record, "sandboxBackend"),
      },
    ];
  });
}

function readSkills(raw: unknown): Skill[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (typeof item !== "object" || item === null) {
      return [];
    }
    const record = item as Record<string, unknown>;
    const name = readString(record, "name");
    if (!name) {
      return [];
    }
    return [
      {
        name,
        description: readString(record, "description"),
        path: readString(record, "path"),
      },
    ];
  });
}

function readSlashCommands(raw: unknown): SlashCommand[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (typeof item !== "object" || item === null) {
      return [];
    }
    const record = item as Record<string, unknown>;
    const name = readString(record, "name");
    if (!name) {
      return [];
    }
    return [{ name, summary: readString(record, "summary") }];
  });
}

function coerceTreeNodes(raw: unknown): SandboxTreeNode[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.flatMap((item) => {
    if (typeof item !== "object" || item === null) {
      return [];
    }
    const record = item as Record<string, unknown>;
    const id = readString(record, "id");
    const label = readString(record, "label");
    const kind = record.kind === "dir" ? "dir" : record.kind === "file" ? "file" : undefined;
    if (!id || !label || !kind) {
      return [];
    }
    const count = typeof record.count === "number" ? record.count : undefined;
    return [
      {
        id,
        label,
        kind,
        count,
        children: coerceTreeNodes(record.children),
      },
    ];
  });
}

function commandOptions(options?: ResetSessionOptions): Record<string, unknown> {
  if (!options) {
    return {};
  }
  return {
    backend: options.backend,
    project_path: options.projectPath,
    ssh_host: options.sshHost,
    ssh_config: options.sshConfig,
    ssh_workdir: options.sshWorkdir,
    image: options.image,
  };
}

function unwrapSubagentEvent(
  event: WireEvent,
): { name: string; inner: WireEvent } | undefined {
  if (event.method !== "SubagentEvent") {
    return undefined;
  }
  const wrapped = event.params.event;
  if (typeof wrapped !== "object" || wrapped === null) {
    return undefined;
  }
  const record = wrapped as Record<string, unknown>;
  const method = readString(record, "method");
  if (!method) {
    return undefined;
  }
  const params =
    typeof record.params === "object" && record.params !== null
      ? (record.params as Record<string, unknown>)
      : {};
  return {
    name: readString(event.params, "name"),
    inner: { method, params },
  };
}

function buildToolPreview(name: string, args: string): string {
  const commandMatch = /"cmd"\s*:\s*"([^"]+)"/.exec(args);
  if (commandMatch) {
    return commandMatch[1];
  }
  return summarize(`${name} ${args}`.trim(), 80) || name;
}

function summarize(text: string, maxLength = 72): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (!compact) {
    return "";
  }
  if (compact.length <= maxLength) {
    return compact;
  }
  return `${compact.slice(0, maxLength)}...`;
}

function toErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
