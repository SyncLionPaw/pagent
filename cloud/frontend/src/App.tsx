import { useEffect, useMemo, useState } from "react";

type User = {
  id: string;
  username: string;
  displayName: string;
};

const TOKEN_KEY = "pagent-cloud-token";

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
    localStorage.removeItem(TOKEN_KEY);
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
        <div className="desktop-shell cloud-shell">
          <div className="cloud-login-workbench">
            <section className="cloud-hero">
              <div className="cloud-hero-mark">Cloud</div>
              <h1 className="cloud-hero-title">pagent Web Cloud</h1>
              <p className="cloud-hero-copy">
                这版是云端前后端分离形态。前端保持 React 风格，视觉尽量向现有
                `editors/web` 靠拢。
              </p>
              <div className="cloud-hero-points">
                <div className="cloud-point">
                  <div className="cloud-point-label">当前阶段</div>
                  <div className="cloud-point-value">登录墙</div>
                </div>
                <div className="cloud-point">
                  <div className="cloud-point-label">鉴权方式</div>
                  <div className="cloud-point-value">JWT Header</div>
                </div>
                <div className="cloud-point">
                  <div className="cloud-point-label">后续主线</div>
                  <div className="cloud-point-value">我的 threads</div>
                </div>
              </div>
            </section>
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
    <div className="desktop-root">
      <div className="desktop-shell cloud-shell">
        <div className="cloud-app-shell">
          <header className="cloud-app-topbar">
            <div>
              <div className="cloud-panel-kicker">pagent cloud</div>
              <div className="cloud-app-title">已进入云端版本</div>
            </div>
            <button className="cloud-secondary-button" type="button" onClick={logout}>
              退出登录
            </button>
          </header>
          <main className="cloud-home-panel">
            <div className="cloud-home-title">你好，{currentUser.displayName}</div>
            <div className="cloud-panel-copy">
              登录墙已经接上。下一步继续补 thread 列表、创建 thread、消息流。
            </div>
            <div className="cloud-hero-points">
              <div className="cloud-point">
                <div className="cloud-point-label">user id</div>
                <div className="cloud-point-value">{currentUser.id}</div>
              </div>
              <div className="cloud-point">
                <div className="cloud-point-label">username</div>
                <div className="cloud-point-value">{currentUser.username}</div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
