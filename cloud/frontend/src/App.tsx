import { useEffect, useMemo, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import WebApp from "../../../editors/web/src/App";

type User = {
  id: string;
  username: string;
  displayName: string;
};

const TOKEN_KEY = "pagent-cloud-token";
const WEB_SERVER_URL_KEY = "pagent-web-server-url";
const WEB_SERVER_TOKEN_KEY = "pagent-web-server-token";

function moveLoginGlow(event: ReactPointerEvent<HTMLDivElement>) {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = `${((event.clientX - rect.left) / rect.width) * 100}%`;
  const y = `${((event.clientY - rect.top) / rect.height) * 100}%`;
  event.currentTarget.style.setProperty("--cloud-hover-x", x);
  event.currentTarget.style.setProperty("--cloud-hover-y", y);
  event.currentTarget.style.setProperty("--cloud-hover-opacity", "1");
}

function resetLoginGlow(event: ReactPointerEvent<HTMLDivElement>) {
  event.currentTarget.style.setProperty("--cloud-hover-opacity", "0");
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail =
      typeof body?.detail === "string" ? body.detail : "request failed";
    throw new Error(detail);
  }
  return body as T;
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState<User>();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(Boolean(token));

  useEffect(() => {
    if (!token) {
      setUser(undefined);
      setChecking(false);
      return;
    }
    setChecking(true);
    api<{ user: User }>("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((data) => {
        setUser(data.user);
        setError("");
      })
      .catch((err: Error) => {
        localStorage.removeItem(TOKEN_KEY);
        setToken("");
        setUser(undefined);
        setError(err.message);
      })
      .finally(() => {
        setChecking(false);
      });
  }, [token]);

  const loggedIn = useMemo(() => Boolean(user && token), [token, user]);

  useEffect(() => {
    if (!token) {
      window.localStorage.removeItem(WEB_SERVER_URL_KEY);
      window.localStorage.removeItem(WEB_SERVER_TOKEN_KEY);
      return;
    }
    window.localStorage.setItem(WEB_SERVER_URL_KEY, "");
    window.localStorage.setItem(WEB_SERVER_TOKEN_KEY, token);
  }, [token]);

  async function onSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const data = await api<{ token: string; user: User }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem(TOKEN_KEY, data.token);
      setToken(data.token);
      setUser(data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "login failed");
    } finally {
      setSubmitting(false);
    }
  }

  function logout() {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(WEB_SERVER_URL_KEY);
    window.localStorage.removeItem(WEB_SERVER_TOKEN_KEY);
    setToken("");
    setUser(undefined);
    setError("");
  }

  if (checking) {
    return (
      <div className="desktop-root">
        <div className="desktop-shell cloud-shell">
          <div className="cloud-loading">正在校验登录态...</div>
        </div>
      </div>
    );
  }

  if (!loggedIn) {
    return (
      <div className="desktop-root">
        <div
          className="desktop-shell cloud-shell"
          onPointerMove={moveLoginGlow}
          onPointerLeave={resetLoginGlow}
        >
          <div className="cloud-login-brand" aria-hidden="true">
            <div className="cloud-login-brand-glow" />
            <img className="cloud-login-brand-image" src="/cloud-logo.png" alt="" />
          </div>
          <div className="cloud-login-shell">
            <section className="cloud-auth-panel">
              <div className="cloud-panel-header">
                <div className="cloud-panel-kicker">登录</div>
                <div className="cloud-panel-title">进入云端版本</div>
                <div className="cloud-panel-copy">
                  当前先用固定演示账户，打通最小登录链路。
                </div>
              </div>
              <form className="cloud-form" onSubmit={onSubmit}>
                <label className="cloud-field">
                  <span className="cloud-field-label">账户</span>
                  <input
                    autoFocus
                    className="cloud-input"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    placeholder="admin"
                  />
                </label>
                <label className="cloud-field">
                  <span className="cloud-field-label">密码</span>
                  <input
                    type="password"
                    className="cloud-input"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="123"
                  />
                </label>
                <div className="cloud-demo-tip">演示账户：admin / 123</div>
                {error ? <div className="cloud-error-box">{error}</div> : null}
                <button className="cloud-primary-button" type="submit" disabled={submitting}>
                  {submitting ? "登录中..." : "登录"}
                </button>
              </form>
            </section>
          </div>
        </div>
      </div>
    );
  }

  const currentUser = user!;

  return (
    <div className="cloud-web-app" data-user-id={currentUser.id} data-user-name={currentUser.username}>
      <button className="cloud-logout-button" type="button" onClick={logout}>
        退出登录
      </button>
      <WebApp />
    </div>
  );
}
