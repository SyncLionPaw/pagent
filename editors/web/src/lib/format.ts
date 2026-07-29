export function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function parseThreadTimestamp(threadId: string): Date | undefined {
  const match =
    /^thread-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/.exec(threadId);
  if (!match) {
    return undefined;
  }
  const [, year, month, day, hour, minute, second] = match;
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  );
}

export function formatRelativeTime(date: Date | undefined): string {
  if (!date) {
    return "";
  }
  const diffMs = Date.now() - date.getTime();
  const diffSeconds = Math.max(0, Math.floor(diffMs / 1000));
  if (diffSeconds < 60) {
    return "刚刚";
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)} 分钟前`;
  }
  if (diffSeconds < 86_400) {
    return `${Math.floor(diffSeconds / 3600)} 小时前`;
  }
  if (diffSeconds < 172_800) {
    return "昨天";
  }
  if (diffSeconds < 604_800) {
    return `${Math.floor(diffSeconds / 86_400)} 天前`;
  }
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const currentYear = new Date().getFullYear();
  if (year === currentYear) {
    return `${month}-${day}`;
  }
  return `${year}-${month}-${day}`;
}

export function projectLabel(path: string): string {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || path || "default";
}

export function readStoredTheme(): "dark" | "light" {
  return window.localStorage.getItem("pagent-web-theme") === "light"
    ? "light"
    : "dark";
}

export function docsUrl(): string {
  return "https://synclionpaw.github.io/pagent/zh/desktop";
}
