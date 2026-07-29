import { Box, Globe, HardDrive, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { NewSessionOptions, ResetSessionOptions, SandboxBackendOption } from "../api/types";

type Props = {
  open: boolean;
  options: NewSessionOptions | undefined;
  projectPath: string;
  onClose: () => void;
  onSubmit: (options: ResetSessionOptions) => void;
};

export function NewSessionModal({ open, options, projectPath, onClose, onSubmit }: Props) {
  const availableBackends = useMemo(
    () => options?.availableBackends ?? (["local", "container", "ssh"] as SandboxBackendOption[]),
    [options],
  );
  const [backend, setBackend] = useState<SandboxBackendOption>("local");
  const [path, setPath] = useState(projectPath);
  const [image, setImage] = useState("pagent:latest");
  const [sshHost, setSshHost] = useState("");
  const [sshWorkdir, setSshWorkdir] = useState("~/pagent");

  useEffect(() => {
    if (!open) {
      return;
    }
    setPath(options?.projectPath || projectPath);
    setBackend(options?.availableBackends?.[0] ?? "local");
    setImage(options?.defaultImage || options?.availableImages?.[0] || "pagent:latest");
    setSshHost(options?.sshHosts?.[0] ?? "");
    setSshWorkdir("~/pagent");
  }, [open, options, projectPath]);

  if (!open) {
    return null;
  }

  const submit = () => {
    const trimmedPath = path.trim();
    if (!trimmedPath) {
      return;
    }
    const payload: ResetSessionOptions = {
      backend,
      projectPath: trimmedPath,
    };
    if (backend === "container" || backend === "docker" || backend === "podman") {
      payload.image = image.trim() || "pagent:latest";
    }
    if (backend === "ssh") {
      payload.sshHost = sshHost.trim();
      payload.sshWorkdir = sshWorkdir.trim() || "~/pagent";
      if (!payload.sshHost) {
        return;
      }
    }
    onSubmit(payload);
  };

  return (
    <div className="desktop-modal is-open">
      <div className="desktop-modal-backdrop" onClick={onClose} />
      <section
        className="desktop-modal-card new-session-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-session-title"
      >
        <div className="desktop-modal-header">
          <div id="new-session-title" className="desktop-modal-title">
            新建任务
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
          {!options ? (
            <div className="thread-meta-loading">正在读取可用运行环境…</div>
          ) : (
            <div className="new-session-form">
              <div className="new-session-field">
                <div className="new-session-label">运行后端</div>
                <div className="new-session-backends">
                  {availableBackends.map((item) => (
                    <button
                      className={`new-session-backend${backend === item ? " active" : ""}`}
                      type="button"
                      key={item}
                      onClick={() => setBackend(item)}
                    >
                      <span className="new-session-backend-icon">{backendIcon(item)}</span>
                      <span className="new-session-backend-copy">
                        <span className="new-session-backend-label">{backendLabel(item)}</span>
                        <span className="new-session-backend-sub">{backendSub(item)}</span>
                      </span>
                    </button>
                  ))}
                </div>
                <div className="new-session-hint">{backendHint(backend)}</div>
              </div>

              <label className="new-session-field">
                <span className="new-session-label">项目路径</span>
                <div className="new-session-path-row">
                  <input
                    className="new-session-input"
                    value={path}
                    onChange={(event) => setPath(event.target.value)}
                    placeholder="/path/to/project"
                  />
                </div>
              </label>

              {backend === "container" || backend === "docker" || backend === "podman" ? (
                <label className="new-session-field">
                  <span className="new-session-label">镜像</span>
                  <input
                    className="new-session-input"
                    value={image}
                    onChange={(event) => setImage(event.target.value)}
                    list="pagent-images"
                    placeholder="pagent:latest"
                  />
                  <datalist id="pagent-images">
                    {options.availableImages.map((item) => (
                      <option value={item} key={item} />
                    ))}
                  </datalist>
                </label>
              ) : null}

              {backend === "ssh" ? (
                <>
                  <label className="new-session-field">
                    <span className="new-session-label">SSH Host</span>
                    <input
                      className="new-session-input"
                      value={sshHost}
                      onChange={(event) => setSshHost(event.target.value)}
                      list="pagent-ssh-hosts"
                      placeholder="my-host"
                    />
                    <datalist id="pagent-ssh-hosts">
                      {options.sshHosts.map((host) => (
                        <option value={host} key={host} />
                      ))}
                    </datalist>
                  </label>
                  <label className="new-session-field">
                    <span className="new-session-label">远程工作目录</span>
                    <input
                      className="new-session-input"
                      value={sshWorkdir}
                      onChange={(event) => setSshWorkdir(event.target.value)}
                      placeholder="~/pagent"
                    />
                  </label>
                </>
              ) : null}

              <div className="new-session-actions">
                <button className="new-session-secondary" type="button" onClick={onClose}>
                  取消
                </button>
                <button className="new-session-primary" type="button" onClick={submit}>
                  开始
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function backendIcon(backend: SandboxBackendOption) {
  if (backend === "ssh") {
    return <Globe className="desktop-icon" aria-hidden="true" />;
  }
  if (backend === "container" || backend === "docker" || backend === "podman") {
    return <Box className="desktop-icon" aria-hidden="true" />;
  }
  return <HardDrive className="desktop-icon" aria-hidden="true" />;
}

function backendLabel(backend: SandboxBackendOption): string {
  if (backend === "local") {
    return "本机";
  }
  if (backend === "container" || backend === "docker" || backend === "podman") {
    return "容器";
  }
  return "远程";
}

function backendSub(backend: SandboxBackendOption): string {
  if (backend === "local") {
    return "local";
  }
  if (backend === "container") {
    return "auto";
  }
  if (backend === "docker" || backend === "podman") {
    return backend;
  }
  return "ssh";
}

function backendHint(backend: SandboxBackendOption): string {
  if (backend === "local") {
    return "命令与文件落在本机 thread workspace，无需 Docker。";
  }
  if (backend === "container" || backend === "docker" || backend === "podman") {
    return "命令在容器内执行；工作区仍挂载到本机 thread workspace。";
  }
  return "通过 SSH 在远端主机执行；需填写 Host 与远程工作目录。";
}
