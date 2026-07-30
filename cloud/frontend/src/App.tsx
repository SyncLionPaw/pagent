import { FormEvent, useEffect, useMemo, useState } from "react";

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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
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
    return <div className="screen shell-center">正在校验登录态...</div>;
  }

  if (!loggedIn) {
    return (
      <div className="screen login-wall">
        <div className="login-card">
          <div className="eyebrow">pagent cloud</div>
          <h1>登录</h1>
          <p className="muted">第一步先做登录墙。当前演示账户固定为 admin / 123。</p>
          <form className="login-form" onSubmit={onSubmit}>
            <label>
              <span>账户</span>
              <input
                autoFocus
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="admin"
              />
            </label>
            <label>
              <span>密码</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="123"
              />
            </label>
            {error ? <div className="error-box">{error}</div> : null}
            <button className="primary-button" type="submit" disabled={submitting}>
              {submitting ? "登录中..." : "登录"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const currentUser = user!;

  return (
    <div className="screen app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">pagent cloud</div>
          <h1>已进入云端版本</h1>
        </div>
        <button className="ghost-button" type="button" onClick={logout}>
          退出登录
        </button>
      </header>
      <main className="content-card">
        <div className="welcome-title">你好，{currentUser.displayName}</div>
        <div className="muted">
          登录墙已经接上。下一步可以继续补 thread 列表、创建 thread、消息流。
        </div>
        <div className="info-grid">
          <div className="info-item">
            <div className="info-label">user id</div>
            <div className="info-value">{currentUser.id}</div>
          </div>
          <div className="info-item">
            <div className="info-label">username</div>
            <div className="info-value">{currentUser.username}</div>
          </div>
        </div>
      </main>
    </div>
  );
}
