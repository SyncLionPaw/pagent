import { X } from "lucide-react";
import type { ThreadMeta, ThreadSummary } from "../api/types";
import { useModalTransition } from "../lib/useModalTransition";

type Props = {
  open: boolean;
  meta: ThreadMeta | undefined;
  session: ThreadSummary | undefined;
  error: string;
  onClose: () => void;
};

/** 对标 desktop openThreadMetaModal / renderThreadMeta，展示会话元信息与原始 metainfo。 */
export function ThreadMetaModal({ open, meta, session, error, onClose }: Props) {
  const { mounted, isOpen } = useModalTransition(open);
  if (!mounted) {
    return null;
  }
  return (
    <div className={`desktop-modal${isOpen ? " is-open" : ""}`}>
      <div className="desktop-modal-backdrop" onClick={onClose} />
      <section
        className="desktop-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="thread-meta-title"
      >
        <div className="desktop-modal-header">
          <div id="thread-meta-title" className="desktop-modal-title">
            会话信息
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
          {error ? (
            <div className="thread-meta-error">{error}</div>
          ) : meta ? (
            <ThreadMetaBody meta={meta} session={session} />
          ) : (
            <MetaSkeleton />
          )}
        </div>
      </section>
    </div>
  );
}

function ThreadMetaBody({
  meta,
  session,
}: {
  meta: ThreadMeta;
  session: ThreadSummary | undefined;
}) {
  const title = meta.title || session?.title || "新建任务";
  const projectPath = session?.projectPath || "";
  const rawMeta = JSON.stringify(meta.metainfo, null, 2);
  return (
    <>
      <div className="thread-meta-summary">
        <div className="thread-meta-title">{title}</div>
        <div className="thread-meta-id">{meta.id}</div>
      </div>
      <div className="thread-meta-grid">
        <div className="thread-meta-label">Project</div>
        <div className="thread-meta-value">{formatMetaValue(projectPath)}</div>
        <div className="thread-meta-label">创建时间</div>
        <div className="thread-meta-value">{formatMetaDate(meta.createdAt)}</div>
        <div className="thread-meta-label">更新时间</div>
        <div className="thread-meta-value">{formatMetaDate(meta.updatedAt)}</div>
        <div className="thread-meta-label">消息数</div>
        <div className="thread-meta-value">{formatMetaValue(meta.messageCount)}</div>
        <div className="thread-meta-label">目录</div>
        <div className="thread-meta-value">{meta.threadPath}</div>
      </div>
      <div className="thread-meta-raw-title">metainfo.json</div>
      <pre className="thread-meta-raw">{rawMeta || "{}"}</pre>
    </>
  );
}

function MetaSkeleton() {
  return (
    <div className="meta-skeleton">
      <div className="meta-skeleton-row">
        <div className="skeleton-line title" />
        <div className="skeleton-line short" />
      </div>
      <div className="meta-skeleton-row">
        <div className="skeleton-line medium" />
        <div className="skeleton-line medium" />
        <div className="skeleton-line short" />
      </div>
      <div className="meta-skeleton-row">
        <div className="skeleton-line short" />
        <div className="skeleton-line block" />
      </div>
    </div>
  );
}

function formatMetaDate(value: string): string {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatMetaValue(value: string | number | undefined): string {
  if (value === undefined || value === "") {
    return "未记录";
  }
  return String(value);
}
