/** 与 desktop protocol.ts 对齐的类型（Web 端）。 */

export type AppInfo = {
  name: string;
  version: string;
  platform: string;
  userName: string;
};

export type RuntimeState = {
  projectPath: string;
  activeHomePath: string;
  activeHomeScope: "user" | "project";
  currentThreadId?: string;
  sandboxBackend?: string;
  sandboxAlive?: boolean;
  yoloMode: boolean;
  bridgeActive: boolean;
  transport: "wire" | "http";
  status: "idle" | "starting" | "ready" | "error";
  lastError?: string;
};

export type ThreadSummary = {
  id: string;
  title: string;
  relativeTime: string;
  projectPath: string;
  sandboxBackend: string;
};

export type ThreadMeta = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount?: number;
  threadPath: string;
  metainfo: Record<string, unknown>;
};

export type ArtifactSummary = {
  id: string;
  name: string;
  path: string;
  size: number;
  mtimeMs: number;
};

export type ArtifactPreview = {
  name: string;
  path: string;
  size: number;
  kind: "text" | "markdown" | "html" | "pdf" | "image" | "binary";
  language?: string;
  text?: string;
  dataUrl?: string;
  truncated?: boolean;
  reason?: string;
};

export type Skill = {
  name: string;
  description: string;
  path: string;
};

export type AppSettings = {
  path: string;
  exists: boolean;
  content: string;
};

export type SandboxStatus = {
  threadId: string;
  backend: string;
  alive: boolean;
  workdir: string;
};

export type SandboxBackendOption = "local" | "container" | "docker" | "podman" | "ssh";

export type EnvironmentCheck = {
  uvInstalled: boolean;
  uvPath?: string;
  pagentInstalled: boolean;
  pagentPath?: string;
  apiKeyConfigured: boolean;
  dockerInstalled: boolean;
  podmanInstalled: boolean;
  containerRuntime?: "docker" | "podman";
  sandboxImage: string;
  sandboxImageExists: boolean;
  configPath: string;
  dataHomePath: string;
  dataHomeLabel: string;
  dataHomeBytes?: number;
  sandboxImageBytes?: number;
};

export type ResetSessionOptions = {
  backend?: SandboxBackendOption;
  projectPath?: string;
  sshHost?: string;
  sshConfig?: string;
  sshWorkdir?: string;
  image?: string;
};

export type NewSessionOptions = {
  projectPath: string;
  availableBackends: SandboxBackendOption[];
  sshHosts: string[];
  defaultImage: string;
  availableImages: string[];
};

export type SandboxTreeNode = {
  id: string;
  label: string;
  kind: "dir" | "file";
  count?: number;
  children?: SandboxTreeNode[];
};

export type WireEvent = {
  method: string;
  params: Record<string, unknown>;
};

export type ProviderSetupInput = {
  apiKey: string;
  model: string;
  baseUrl?: string;
};
