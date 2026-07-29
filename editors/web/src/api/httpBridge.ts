import type { WireEvent } from "./types";

export type BridgeCallbacks = {
  onEvent: (event: WireEvent) => void;
  onError: (error: Error) => void;
  onClose: () => void;
};

/**
 * 浏览器版 HttpBridge：POST /command + GET /events SSE。
 * 对齐 desktop shared/agent.ts：等首帧再冲刷排队命令。
 */
export class HttpBridge {
  private abort: AbortController | undefined;
  private ready = false;
  private pending: object[] = [];
  private stopping = false;

  constructor(
    private readonly baseUrl: string,
    private readonly token: string | undefined,
    private readonly callbacks: BridgeCallbacks,
  ) {}

  start(): void {
    this.stopping = false;
    this.ready = false;
    this.pending = [];
    this.abort = new AbortController();
    void this.openEvents();
  }

  send(command: object): void {
    if (this.stopping) {
      return;
    }
    if (!this.ready) {
      this.pending.push(command);
      return;
    }
    void this.post(command);
  }

  stop(): void {
    this.stopping = true;
    this.abort?.abort();
    this.abort = undefined;
    this.pending = [];
  }

  private authHeaders(): Record<string, string> {
    const token = this.token?.trim();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  private async post(command: object): Promise<void> {
    try {
      const res = await fetch(`${this.baseUrl}/command`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...this.authHeaders(),
        },
        body: JSON.stringify(command),
        signal: this.abort?.signal,
      });
      if (!res.ok) {
        this.callbacks.onError(new Error(`POST /command -> ${res.status}`));
      }
    } catch (error) {
      if (!this.stopping) {
        this.callbacks.onError(toError(error));
      }
    }
  }

  private async openEvents(): Promise<void> {
    try {
      const res = await fetch(`${this.baseUrl}/events`, {
        method: "GET",
        headers: {
          Accept: "text/event-stream",
          ...this.authHeaders(),
        },
        signal: this.abort?.signal,
      });
      if (!res.ok || !res.body) {
        this.callbacks.onError(new Error(`GET /events -> ${res.status}`));
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          const frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          this.emitFrame(frame);
          boundary = buffer.indexOf("\n\n");
        }
      }
      if (!this.stopping) {
        this.callbacks.onClose();
      }
    } catch (error) {
      if (!this.stopping) {
        this.callbacks.onError(toError(error));
      }
    }
  }

  private emitFrame(frame: string): void {
    for (const rawLine of frame.split("\n")) {
      if (!rawLine.startsWith("data:")) {
        continue;
      }
      const line = rawLine.slice(5).trim();
      if (!line) {
        continue;
      }
      try {
        const parsed = JSON.parse(line) as {
          jsonrpc?: string;
          method?: string;
          params?: Record<string, unknown>;
          id?: unknown;
        };
        if (parsed.id !== undefined || typeof parsed.method !== "string") {
          continue;
        }
        this.callbacks.onEvent({
          method: parsed.method,
          params: parsed.params ?? {},
        });
      } catch {
        // ignore malformed
      }
    }
    this.markReady();
  }

  private markReady(): void {
    if (this.ready) {
      return;
    }
    this.ready = true;
    const queued = this.pending;
    this.pending = [];
    for (const command of queued) {
      void this.post(command);
    }
  }
}

function toError(value: unknown): Error {
  return value instanceof Error ? value : new Error(String(value));
}

export function normalizeBaseUrl(raw: string): string {
  const trimmed = raw.trim() || "";
  if (!trimmed) {
    // 同域部署时走相对路径
    return "";
  }
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;
  return withScheme.replace(/\/+$/, "");
}

export function parseWireLine(line: string): WireEvent | undefined {
  try {
    const parsed = JSON.parse(line) as {
      method?: string;
      params?: Record<string, unknown>;
      id?: unknown;
    };
    if (parsed.id !== undefined || typeof parsed.method !== "string") {
      return undefined;
    }
    return { method: parsed.method, params: parsed.params ?? {} };
  } catch {
    return undefined;
  }
}
