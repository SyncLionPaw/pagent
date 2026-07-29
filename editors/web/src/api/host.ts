import type {
  AppInfo,
  AppSettings,
  ArtifactPreview,
  ArtifactSummary,
  NewSessionOptions,
  RuntimeState,
  ThreadMeta,
  WireEvent,
} from "./types";

function authHeaders(token?: string): HeadersInit {
  return token?.trim() ? { Authorization: `Bearer ${token.trim()}` } : {};
}

async function apiGet<T>(
  baseUrl: string,
  path: string,
  token?: string,
  query?: Record<string, string | undefined>,
): Promise<T> {
  const url = new URL(`${baseUrl}${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }
  const res = await fetch(url, { headers: { ...authHeaders(token) } });
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`);
  }
  return (await res.json()) as T;
}

async function apiPost<T>(
  baseUrl: string,
  path: string,
  body: unknown,
  token?: string,
): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`);
  }
  return (await res.json()) as T;
}

export function createHostApi(baseUrl: string, token?: string) {
  return {
    getAppInfo: () => apiGet<AppInfo>(baseUrl, "/api/app-info", token),
    getRuntimeState: () => apiGet<RuntimeState>(baseUrl, "/api/runtime-state", token),
    getSettings: () => apiGet<AppSettings>(baseUrl, "/api/settings", token),
    listArtifacts: (projectPath?: string) =>
      apiGet<ArtifactSummary[]>(baseUrl, "/api/artifacts", token, { project_path: projectPath }),
    readArtifact: (path: string, projectPath?: string) =>
      apiGet<ArtifactPreview>(baseUrl, "/api/artifacts/read", token, {
        path,
        project_path: projectPath,
      }),
    listProjectFiles: (projectPath?: string) =>
      apiGet<string[]>(baseUrl, "/api/project-files", token, { project_path: projectPath }),
    listProjectTree: (projectPath?: string) =>
      apiGet(baseUrl, "/api/project-tree", token, { project_path: projectPath }),
    getNewSessionOptions: (projectPath?: string) =>
      apiGet<NewSessionOptions>(baseUrl, "/api/new-session-options", token, {
        project_path: projectPath,
      }),
    getThreadMeta: (threadId: string) =>
      apiGet<ThreadMeta>(baseUrl, `/api/thread-meta/${encodeURIComponent(threadId)}`, token),
    setYoloMode: (enabled: boolean) =>
      apiPost<{ yoloMode: boolean }>(baseUrl, "/api/yolo", { enabled }, token),
    setProjectPath: (projectPath: string) =>
      apiPost<{ projectPath: string }>(baseUrl, "/api/project-path", { projectPath }, token),
  };
}

export type HostApi = ReturnType<typeof createHostApi>;

export function readString(params: Record<string, unknown>, key: string): string {
  const value = params[key];
  return typeof value === "string" ? value : "";
}

export function unwrapSubagentEvent(
  event: WireEvent,
): { name: string; conversationId: string; inner: WireEvent } | undefined {
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
    conversationId: readString(event.params, "conversation_id"),
    inner: { method, params },
  };
}
