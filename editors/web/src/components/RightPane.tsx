import DOMPurify from "dompurify";
import { marked } from "marked";
import type { CSSProperties, ReactNode } from "react";
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  CodeXml,
  Copy,
  Cpu,
  Database,
  Download,
  File,
  FileJson,
  FileText,
  Folder,
  FolderOpen,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type {
  ArtifactPreview,
  ArtifactSummary,
  RuntimeState,
  SandboxStatus,
  SandboxTreeNode,
} from "../api/types";
import { formatBytes } from "../lib/format";
import { highlightCode } from "../lib/highlight";
import { toast } from "../lib/toast";

export type RightTab = "project" | "sandbox" | "terminal";
export type ProjectPane = "files" | "artifacts";
export type ActivityState = "running" | "sleeping" | "error";
export type TerminalEntry = {
  kind: "command" | "stdout" | "stderr" | "status";
  text: string;
};

type Props = {
  activeTab: RightTab;
  projectPane: ProjectPane;
  runtime: RuntimeState;
  projectTree: SandboxTreeNode[];
  sandboxTree: SandboxTreeNode[];
  sandboxStatus: SandboxStatus;
  artifacts: ArtifactSummary[];
  artifactPreview: ArtifactPreview | undefined;
  terminalEntries: TerminalEntry[];
  activityState: ActivityState;
  onTabChange: (tab: RightTab) => void;
  onProjectPaneChange: (pane: ProjectPane) => void;
  onToggleCollapsed: () => void;
  onRefreshProject: () => void;
  onRefreshSandbox: () => void;
  onPreviewArtifact: (path: string) => void;
  onCloseArtifactPreview: () => void;
};

export function RightPane({
  activeTab,
  projectPane,
  runtime,
  projectTree,
  sandboxTree,
  sandboxStatus,
  artifacts,
  artifactPreview,
  terminalEntries,
  activityState,
  onTabChange,
  onProjectPaneChange,
  onToggleCollapsed,
  onRefreshProject,
  onRefreshSandbox,
  onPreviewArtifact,
  onCloseArtifactPreview,
}: Props) {
  const [expandedProject, setExpandedProject] = useState<ReadonlySet<string>>(new Set());
  const [expandedSandbox, setExpandedSandbox] = useState<ReadonlySet<string>>(new Set());
  const [projectBusy, setProjectBusy] = useState(false);
  const [sandboxBusy, setSandboxBusy] = useState(false);
  const resources = resourceSnapshot(activityState);

  const toggleProject = (id: string) =>
    setExpandedProject((current) => toggleSet(current, id));
  const toggleSandbox = (id: string) =>
    setExpandedSandbox((current) => toggleSet(current, id));

  // 每次目录树刷新后自动展开顶层目录，并撤下刷新按钮的忙碌态。
  useEffect(() => {
    setExpandedProject((current) => expandTopLevel(current, projectTree));
    setProjectBusy(false);
  }, [projectTree]);
  useEffect(() => {
    setExpandedSandbox((current) => expandTopLevel(current, sandboxTree));
    setSandboxBusy(false);
  }, [sandboxTree]);
  useEffect(() => {
    setProjectBusy(false);
  }, [artifacts]);

  const handleRefreshProject = () => {
    setProjectBusy(true);
    onRefreshProject();
  };
  const handleRefreshSandbox = () => {
    setSandboxBusy(true);
    onRefreshSandbox();
  };

  return (
    <aside className="pane pane-right" data-right-pane>
      <div className="pane-expanded">
        <div className="pane-topbar right-topbar">
          <div className="tab-group" role="tablist" aria-label="右侧面板">
            <TabButton tab="project" activeTab={activeTab} onTabChange={onTabChange}>
              项目
            </TabButton>
            <TabButton tab="sandbox" activeTab={activeTab} onTabChange={onTabChange}>
              沙箱
            </TabButton>
            <TabButton tab="terminal" activeTab={activeTab} onTabChange={onTabChange}>
              Log
            </TabButton>
          </div>
        </div>

        <div className="right-content">
          <section className={`right-view${activeTab === "project" ? " active" : ""}`}>
            <div className={`project-host${artifactPreview ? " preview-open" : ""}`} data-project-pane={projectPane}>
              <div className="file-panel-header project-host-header">
                <div
                  className="jelly-switch"
                  data-pane={projectPane}
                  role="tablist"
                  aria-label="项目视图"
                >
                  <span className="jelly-switch-thumb" aria-hidden="true" />
                  <button
                    type="button"
                    className={`jelly-switch-option${projectPane === "files" ? " active" : ""}`}
                    role="tab"
                    aria-selected={projectPane === "files"}
                    onClick={() => onProjectPaneChange("files")}
                  >
                    目录
                  </button>
                  <button
                    type="button"
                    className={`jelly-switch-option${projectPane === "artifacts" ? " active" : ""}`}
                    role="tab"
                    aria-selected={projectPane === "artifacts"}
                    onClick={() => onProjectPaneChange("artifacts")}
                  >
                    产物 <span className="tab-badge">{artifacts.length}</span>
                  </button>
                </div>
                <button
                  className={`file-panel-refresh${projectBusy ? " is-busy" : ""}`}
                  type="button"
                  title={projectPane === "files" ? "刷新项目目录" : "刷新产物"}
                  aria-label={projectPane === "files" ? "刷新项目目录" : "刷新产物"}
                  onClick={handleRefreshProject}
                >
                  <RefreshCw className="desktop-icon" aria-hidden="true" />
                </button>
              </div>
              <div className="file-panel project-files-pane" hidden={projectPane !== "files"}>
                <div className="file-tree">
                  <PathRootCard rootPath={runtime.projectPath} label="本机路径" />
                  {projectTree.length === 0 ? (
                    <Empty title="项目目录为空" copy="绑定项目后，这里会展示项目目录树。" />
                  ) : (
                    <TreeRows nodes={projectTree} expanded={expandedProject} onToggle={toggleProject} />
                  )}
                </div>
              </div>
              <div
                className={`artifacts-panel project-artifacts-pane${artifactPreview ? " preview-open" : ""}`}
                hidden={projectPane !== "artifacts"}
              >
                <div className="artifacts-list">
                  <PathRootCard rootPath={artifactRootPath(runtime.projectPath)} label="本机路径" />
                  {artifacts.length === 0 ? (
                    <Empty copy="当前项目还没有产物。" />
                  ) : (
                    artifacts.map((artifact) => (
                      <button
                        className="artifact-row"
                        key={artifact.path}
                        type="button"
                        title={`预览 ${artifact.name}`}
                        onClick={() => onPreviewArtifact(artifact.path)}
                      >
                        <span className="artifact-icon">
                          <ArtifactIcon name={artifact.name} />
                        </span>
                        <div className="artifact-main">
                          <div className="artifact-name">{artifact.name}</div>
                          <div className="artifact-meta">
                            {formatBytes(artifact.size)} · {new Date(artifact.mtimeMs).toLocaleString()}
                          </div>
                        </div>
                        <span
                          className="artifact-open"
                          title="复制路径"
                          role="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            void copyPath(artifact.path);
                          }}
                        >
                          <Copy className="desktop-icon" aria-hidden="true" />
                        </span>
                      </button>
                    ))
                  )}
                </div>
                <div className="artifact-preview" hidden={!artifactPreview}>
                  {artifactPreview ? (
                    <ArtifactPreviewCard
                      preview={artifactPreview}
                      onClose={onCloseArtifactPreview}
                    />
                  ) : null}
                </div>
              </div>
            </div>
          </section>

          <section className={`right-view${activeTab === "sandbox" ? " active" : ""}`}>
            <div className="file-panel">
              <div className="file-panel-header">
                <span>文件系统</span>
                <button
                  className={`file-panel-refresh${sandboxBusy ? " is-busy" : ""}`}
                  type="button"
                  title="刷新沙箱文件"
                  aria-label="刷新沙箱文件"
                  onClick={handleRefreshSandbox}
                >
                  <RefreshCw className="desktop-icon" aria-hidden="true" />
                </button>
              </div>
              <div className="file-tree">
                <PathRootCard
                  rootPath={sandboxStatus.workdir || (runtime.currentThreadId ? "待连接" : "未启动")}
                  label={sandboxPathRootLabel(sandboxStatus.backend || runtime.sandboxBackend || "")}
                />
                {sandboxTree.length === 0 ? (
                  <Empty
                    title="沙箱里还没有文件"
                    copy="沙箱连接后，这里会展示当前 workdir 的目录树。"
                  />
                ) : (
                  <TreeRows nodes={sandboxTree} expanded={expandedSandbox} onToggle={toggleSandbox} />
                )}
              </div>
            </div>
          </section>

          <section className={`right-view${activeTab === "terminal" ? " active" : ""}`}>
            <div className="terminal-panel">
              <div className="terminal-view-panel">
                <div className="file-panel-header">终端输出</div>
                <div className="terminal-scroll">
                  {terminalEntries.length === 0 ? (
                    <div className="terminal-empty">命令执行后，这里会显示最新输出。</div>
                  ) : (
                    terminalEntries.map((entry, index) => (
                      <div className={`terminal-line terminal-line-${entry.kind}`} key={`${entry.kind}-${index}`}>
                        <span className="terminal-prefix">{entry.kind === "command" ? "$" : ">"}</span>
                        <span className="terminal-text">{entry.text}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>

        <div className="right-footer" data-tab={activeTab}>
          <div className={`resource-strip${activeTab === "project" && projectPane === "artifacts" ? " hidden" : ""}`}>
            <ResourceItem icon={<Zap className="desktop-icon" />} value={resources.cpu.value} percent={resources.cpu.percent} />
            <ResourceItem icon={<Cpu className="desktop-icon" />} value={resources.memory.value} percent={resources.memory.percent} />
            <ResourceItem icon={<Database className="desktop-icon" />} value={resources.disk.value} percent={resources.disk.percent} />
          </div>
          <button
            className="icon-button collapse-right-button"
            type="button"
            title="折叠右栏"
            onClick={onToggleCollapsed}
          >
            <PanelRightClose className="desktop-icon" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="pane-collapsed">
        <button className="collapsed-icon" type="button" title="项目" onClick={() => onTabChange("project")}>
          <Folder className="desktop-icon" aria-hidden="true" />
        </button>
        <button className="collapsed-icon" type="button" title="沙箱" onClick={() => onTabChange("sandbox")}>
          <FolderOpen className="desktop-icon" aria-hidden="true" />
        </button>
        <button
          className="collapsed-expand collapsed-expand-bottom"
          type="button"
          title="展开右栏"
          onClick={onToggleCollapsed}
        >
          <PanelRightOpen className="desktop-icon" aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}

function TabButton({
  tab,
  activeTab,
  onTabChange,
  children,
}: {
  tab: RightTab;
  activeTab: RightTab;
  onTabChange: (tab: RightTab) => void;
  children: string;
}) {
  return (
    <button
      className={`tab-button${activeTab === tab ? " active" : ""}`}
      type="button"
      role="tab"
      aria-selected={activeTab === tab}
      onClick={() => onTabChange(tab)}
    >
      {children}
    </button>
  );
}

function PathRootCard({ rootPath, label }: { rootPath: string; label: string }) {
  if (!rootPath) {
    return null;
  }
  return (
    <div className="artifact-root">
      <div className="artifact-root-label">{label}</div>
      <div className="artifact-root-path" title={rootPath}>
        {rootPath}
      </div>
    </div>
  );
}

function Empty({ title, copy }: { title?: string; copy: string }) {
  return (
    <div className="session-empty">
      {title ? <div className="session-empty-title">{title}</div> : null}
      <div className="session-empty-copy">{copy}</div>
    </div>
  );
}

function TreeRows({
  nodes,
  expanded,
  onToggle,
  depth = 0,
}: {
  nodes: SandboxTreeNode[];
  expanded: ReadonlySet<string>;
  onToggle: (id: string) => void;
  depth?: number;
}) {
  return (
    <>
      {nodes.map((node) => {
        const indent = depth * 18;
        if (node.kind === "dir") {
          const open = expanded.has(node.id);
          return (
            <div className="tree-block" key={node.id}>
              <button
                className="tree-row tree-row-dir"
                type="button"
                style={{ "--tree-indent": `${indent}px` } as CSSProperties}
                onClick={() => onToggle(node.id)}
              >
                <span className="tree-cell tree-cell-arrow">
                  {open ? (
                    <ChevronDown className="desktop-icon" aria-hidden="true" />
                  ) : (
                    <ChevronRight className="desktop-icon" aria-hidden="true" />
                  )}
                </span>
                <span className="tree-cell tree-cell-icon">
                  <Folder className="desktop-icon" aria-hidden="true" />
                </span>
                <span className="tree-cell tree-cell-label">{node.label}</span>
                <span className="tree-count">{node.count ?? 0}</span>
              </button>
              {open && node.children ? (
                <TreeRows nodes={node.children} expanded={expanded} onToggle={onToggle} depth={depth + 1} />
              ) : null}
            </div>
          );
        }
        return (
          <div
            className="tree-row tree-row-file"
            key={node.id}
            style={{ "--tree-indent": `${indent}px` } as CSSProperties}
          >
            <span className="tree-cell tree-cell-arrow" />
            <span className="tree-cell tree-cell-icon">
              <File className="desktop-icon" aria-hidden="true" />
            </span>
            <span className="tree-cell tree-cell-label">{node.label}</span>
            <span className="tree-change" />
          </div>
        );
      })}
    </>
  );
}

function ArtifactPreviewCard({
  preview,
  onClose,
}: {
  preview: ArtifactPreview;
  onClose: () => void;
}) {
  const markdown = useMemo(() => {
    if (preview.kind !== "markdown") {
      return "";
    }
    return DOMPurify.sanitize(marked.parse(preview.text ?? "", { async: false }));
  }, [preview.kind, preview.text]);
  const highlighted = useMemo(() => {
    if (preview.kind !== "text") {
      return "";
    }
    return highlightCode(preview.text ?? "", preview.language);
  }, [preview.kind, preview.text, preview.language]);
  const downloadable = Boolean(preview.dataUrl);
  return (
    <>
      <div className="artifact-preview-head">
        <button
          className="artifact-preview-back"
          type="button"
          title="返回列表"
          aria-label="返回列表"
          onClick={onClose}
        >
          <ArrowLeft className="desktop-icon" aria-hidden="true" />
        </button>
        <span className="artifact-preview-icon">
          <ArtifactIcon name={preview.name} />
        </span>
        <span className="artifact-preview-name" title={preview.path}>
          {preview.name}
        </span>
        <span className="artifact-preview-meta">
          {formatBytes(preview.size)}
          {preview.language ? ` · ${preview.language}` : ""}
        </span>
        <button
          className="artifact-preview-open"
          type="button"
          title={downloadable ? "下载文件" : "复制路径"}
          aria-label={downloadable ? "下载文件" : "复制路径"}
          onClick={() => {
            if (downloadable && preview.dataUrl) {
              downloadDataUrl(preview.dataUrl, preview.name);
            } else {
              void copyPath(preview.path);
            }
          }}
        >
          {downloadable ? (
            <Download className="desktop-icon" aria-hidden="true" />
          ) : (
            <Copy className="desktop-icon" aria-hidden="true" />
          )}
        </button>
      </div>
      {preview.truncated ? (
        <div className="artifact-preview-note">内容较大，仅显示前 512KB。</div>
      ) : null}
      {preview.kind === "image" && preview.dataUrl ? (
        <div className="artifact-preview-body artifact-preview-image">
          <img src={preview.dataUrl} alt={preview.name} />
        </div>
      ) : preview.kind === "pdf" && preview.dataUrl ? (
        <div className="artifact-preview-body artifact-preview-frame">
          <iframe src={preview.dataUrl} title={preview.name} />
        </div>
      ) : preview.kind === "html" && preview.dataUrl ? (
        <div className="artifact-preview-body artifact-preview-frame">
          <iframe src={preview.dataUrl} title={preview.name} sandbox="allow-scripts allow-popups allow-forms" />
        </div>
      ) : preview.kind === "markdown" ? (
        <div className="artifact-preview-body">
          <div
            className="artifact-preview-markdown markdown-body"
            dangerouslySetInnerHTML={{ __html: markdown }}
          />
        </div>
      ) : preview.kind === "text" ? (
        <div className="artifact-preview-body">
          <pre className="artifact-preview-code hljs">
            <code dangerouslySetInnerHTML={{ __html: highlighted }} />
          </pre>
        </div>
      ) : (
        <div className="artifact-preview-body artifact-preview-empty">
          {preview.reason ?? "无法内联预览此文件。"}
        </div>
      )}
    </>
  );
}

function ResourceItem({
  icon,
  value,
  percent,
}: {
  icon: ReactNode;
  value: string;
  percent: number;
}) {
  return (
    <div className="resource-item">
      <span className="resource-icon">{icon}</span>
      <div className="resource-track">
        <span style={{ width: `${percent}%` }} />
      </div>
      <span className="resource-value">{value}</span>
    </div>
  );
}

function toggleSet(current: ReadonlySet<string>, id: string): ReadonlySet<string> {
  const next = new Set(current);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  return next;
}

function artifactRootPath(projectPath: string): string {
  if (!projectPath) {
    return "";
  }
  const separator = projectPath.includes("\\") ? "\\" : "/";
  return `${projectPath.replace(/[\\/]+$/, "")}${separator}artifacts`;
}

function sandboxPathRootLabel(backend: string): string {
  if (backend === "local") {
    return "本机沙箱";
  }
  if (backend === "container" || backend === "docker" || backend === "podman") {
    return "容器沙箱";
  }
  if (backend === "ssh") {
    return "SSH 沙箱";
  }
  return "沙箱";
}

function resourceSnapshot(activityState: ActivityState) {
  if (activityState === "running") {
    return {
      cpu: { value: "41%", percent: 41 },
      memory: { value: "1.3 GB", percent: 57 },
      disk: { value: "2.4 GB", percent: 34 },
    };
  }
  if (activityState === "error") {
    return {
      cpu: { value: "--", percent: 12 },
      memory: { value: "--", percent: 18 },
      disk: { value: "2.4 GB", percent: 34 },
    };
  }
  return {
    cpu: { value: "0%", percent: 0 },
    memory: { value: "0 GB", percent: 0 },
    disk: { value: "2.4 GB", percent: 34 },
  };
}

function expandTopLevel(
  current: ReadonlySet<string>,
  nodes: SandboxTreeNode[],
): ReadonlySet<string> {
  const next = new Set(current);
  for (const node of nodes) {
    if (node.kind === "dir") {
      next.add(node.id);
    }
  }
  return next;
}

async function copyPath(path: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(path);
    toast("已复制路径", { type: "success" });
  } catch {
    toast("复制失败", { type: "error" });
  }
}

function downloadDataUrl(dataUrl: string, name: string): void {
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function ArtifactIcon({ name }: { name: string }) {
  if (/\.(html?|css|jsx?|tsx?|py|sh)$/i.test(name)) {
    return <CodeXml className="desktop-icon" aria-hidden="true" />;
  }
  if (/\.json$/i.test(name)) {
    return <FileJson className="desktop-icon" aria-hidden="true" />;
  }
  if (/\.(md|txt|log)$/i.test(name)) {
    return <FileText className="desktop-icon" aria-hidden="true" />;
  }
  return <File className="desktop-icon" aria-hidden="true" />;
}
