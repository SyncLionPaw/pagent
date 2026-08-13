import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { AppSettings, EnvironmentCheck, ProviderOption } from "../api/types";
import { formatBytes } from "../lib/format";

export type ConfigSnapshot = {
  provider?: {
    name?: string;
    kind?: string;
    model?: string;
    base_url?: string;
    api_key_configured?: boolean;
    api_key_masked?: string;
  };
  providers?: ProviderOption[];
  sandbox?: Record<string, unknown>;
  runner?: Record<string, unknown>;
  permission?: Record<string, unknown>;
  project?: Record<string, unknown>;
};

type Props = {
  open: boolean;
  settings: AppSettings | undefined;
  environment: EnvironmentCheck | undefined;
  config: ConfigSnapshot | undefined;
  serverUrl: string;
  token: string;
  onClose: () => void;
  onSaveConnection: (serverUrl: string, token: string) => void;
  onRefreshEnvironment: () => void;
};

export function SettingsModal({
  open,
  settings,
  environment,
  config,
  serverUrl,
  token,
  onClose,
  onSaveConnection,
  onRefreshEnvironment,
}: Props) {
  const [draftUrl, setDraftUrl] = useState(serverUrl);
  const [draftToken, setDraftToken] = useState(token);

  useEffect(() => {
    if (!open) {
      return;
    }
    setDraftUrl(serverUrl);
    setDraftToken(token);
  }, [open, serverUrl, token]);

  if (!open) {
    return null;
  }

  return (
    <div className="desktop-modal is-open">
      <div className="desktop-modal-backdrop" onClick={onClose} />
      <section
        className="desktop-modal-card settings-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <div className="desktop-modal-header">
          <div id="settings-title" className="desktop-modal-title">
            设置
          </div>
          <button
            className="modal-close-button"
            type="button"
            title="关闭"
            aria-label="关闭"
            onClick={onClose}
          >
            <X className="desktop-icon" aria-hidden="true" />
          </button>
        </div>
        <div className="desktop-modal-body">
          <div className="settings-section">
            <div className="settings-section-title">连接</div>
            <div className="new-session-form">
              <label className="new-session-field">
                <span className="new-session-label">Server URL</span>
                <input
                  className="new-session-input"
                  value={draftUrl}
                  placeholder="留空表示同源 / http://127.0.0.1:8848"
                  onChange={(event) => setDraftUrl(event.target.value)}
                />
              </label>
              <label className="new-session-field">
                <span className="new-session-label">Token</span>
                <input
                  className="new-session-input"
                  value={draftToken}
                  type="password"
                  placeholder="PAGENT_SERVER_TOKEN"
                  onChange={(event) => setDraftToken(event.target.value)}
                />
              </label>
              <div className="new-session-actions">
                <button
                  className="new-session-secondary"
                  type="button"
                  onClick={() => onSaveConnection(draftUrl, draftToken)}
                >
                  保存并重连
                </button>
              </div>
            </div>
          </div>

          <div className="settings-section">
            <div className="settings-section-title">环境</div>
            <button className="new-session-secondary" type="button" onClick={onRefreshEnvironment}>
              刷新环境检查
            </button>
            {environment ? (
              <div className="settings-list">
                <StatusEntry label="uv" ok={environment.uvInstalled} value={environment.uvPath} />
                <StatusEntry
                  label="pagent CLI"
                  ok={environment.pagentInstalled}
                  value={environment.pagentPath}
                />
                <StatusEntry
                  label="API Key"
                  ok={environment.apiKeyConfigured}
                  value={environment.configPath}
                />
                <StatusEntry
                  label="Docker"
                  ok={environment.dockerInstalled}
                  value={environment.containerRuntime}
                />
                <StatusEntry label="Podman" ok={environment.podmanInstalled} />
                <div className="settings-entry">
                  <span className="settings-key">数据目录</span>
                  <span className="settings-value">
                    {environment.dataHomeLabel || environment.dataHomePath}
                    {typeof environment.dataHomeBytes === "number"
                      ? ` · ${formatBytes(environment.dataHomeBytes)}`
                      : ""}
                  </span>
                </div>
              </div>
            ) : (
              <div className="settings-empty">等待 environment_check 返回…</div>
            )}
          </div>

          <div className="settings-section">
            <div className="settings-section-title">模型服务</div>
            <div className="settings-list">
              <div className="settings-entry">
                <span className="settings-key">模型</span>
                <span className="settings-value">{config?.provider?.model || "未配置"}</span>
              </div>
              <div className="settings-entry">
                <span className="settings-key">Base URL</span>
                <span className="settings-value">{config?.provider?.base_url || "默认"}</span>
              </div>
              <div className="settings-entry">
                <span className="settings-key">API Key</span>
                <span className="settings-value">
                  {config?.provider?.api_key_configured
                    ? config.provider.api_key_masked || "已配置"
                    : "未配置"}
                </span>
              </div>
            </div>
          </div>

          <div className="settings-section">
            <div className="settings-section-title">配置文件</div>
            {settings ? (
              <>
                <div className="settings-path">{settings.path}</div>
                <pre className="settings-raw">{settings.content || "(空)"}</pre>
              </>
            ) : (
              <div className="settings-empty">正在读取设置…</div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function StatusEntry({
  label,
  ok,
  value,
}: {
  label: string;
  ok: boolean;
  value?: string;
}) {
  return (
    <div className="settings-entry">
      <span className="settings-key">
        {ok ? (
          <CheckCircle2 className="desktop-icon" aria-hidden="true" />
        ) : (
          <CircleAlert className="desktop-icon" aria-hidden="true" />
        )}{" "}
        {label}
      </span>
      <span className="settings-value">{value || (ok ? "可用" : "不可用")}</span>
    </div>
  );
}
