import { KeyRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { EnvironmentCheck, ProviderSetupInput } from "../api/types";
import type { ConfigSnapshot } from "./SettingsModal";

type Props = {
  open: boolean;
  blocked: boolean;
  environment: EnvironmentCheck | undefined;
  config: ConfigSnapshot | undefined;
  onSubmit: (setup: ProviderSetupInput) => void;
  onClose: () => void;
};

export function Onboarding({
  open,
  blocked,
  environment,
  config,
  onSubmit,
  onClose,
}: Props) {
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("deepseek-chat");
  const [baseUrl, setBaseUrl] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }
    setModel(config?.provider?.model || "deepseek-chat");
    setBaseUrl(config?.provider?.base_url || "");
  }, [open, config]);

  if (!open) {
    return null;
  }

  const submit = () => {
    const key = apiKey.trim();
    if (!key) {
      return;
    }
    onSubmit({
      apiKey: key,
      model: model.trim() || "deepseek-chat",
      baseUrl: baseUrl.trim() || undefined,
    });
    setApiKey("");
  };

  return (
    <div className="desktop-modal setup-guard-modal is-open">
      <div className="desktop-modal-backdrop setup-guard-backdrop" />
      <section
        className="desktop-modal-card onboarding-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
      >
        <div className="desktop-modal-header">
          <div id="onboarding-title" className="desktop-modal-title">
            首次设置
          </div>
          {!blocked ? (
            <button
              className="modal-close-button"
              type="button"
              title="关闭"
              aria-label="关闭"
              onClick={onClose}
            >
              <X className="desktop-icon" aria-hidden="true" />
            </button>
          ) : null}
        </div>
        <div className="desktop-modal-body">
          <div className="setup-pane">
            <div className="setup-hero">
              <div className="setup-hero-icon">
                <KeyRound className="desktop-icon" aria-hidden="true" />
              </div>
              <div>
                <div className="setup-title">配置模型服务</div>
                <p className="setup-lead">
                  pagent 需要 API Key 才能开始任务。密钥会写入服务端配置文件，不会回传明文。
                </p>
              </div>
            </div>

            <div className="settings-list">
              <div className="settings-entry">
                <span className="settings-key">配置文件</span>
                <span className="settings-value">
                  {environment?.configPath || "等待 environment_check…"}
                </span>
              </div>
              <div className="settings-entry">
                <span className="settings-key">当前状态</span>
                <span className="settings-value">
                  {environment?.apiKeyConfigured || config?.provider?.api_key_configured
                    ? "已配置"
                    : "未配置"}
                </span>
              </div>
            </div>

            <div className="new-session-form">
              <label className="new-session-field">
                <span className="new-session-label">API Key</span>
                <input
                  className="new-session-input"
                  type="password"
                  value={apiKey}
                  autoFocus
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="sk-..."
                />
              </label>
              <label className="new-session-field">
                <span className="new-session-label">Model</span>
                <input
                  className="new-session-input"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder="deepseek-chat"
                />
              </label>
              <label className="new-session-field">
                <span className="new-session-label">Base URL</span>
                <input
                  className="new-session-input"
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  placeholder="留空使用默认 OpenAI 兼容地址"
                />
              </label>
              <div className="new-session-actions">
                {!blocked ? (
                  <button className="new-session-secondary" type="button" onClick={onClose}>
                    稍后再说
                  </button>
                ) : null}
                <button className="new-session-primary" type="button" onClick={submit}>
                  保存并继续
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
