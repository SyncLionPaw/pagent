import { CircleAlert } from "lucide-react";
import { useModalTransition } from "../lib/useModalTransition";

export type ConfirmOptions = {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  tone?: "danger" | "primary";
};

type Props = {
  open: boolean;
  options: ConfirmOptions;
  onCancel: () => void;
  onConfirm: () => void;
};

/** 对标 desktop openConfirm 的自定义二次确认框，替代 window.confirm。 */
export function ConfirmModal({ open, options, onCancel, onConfirm }: Props) {
  const { mounted, isOpen } = useModalTransition(open);
  if (!mounted) {
    return null;
  }
  const danger = options.tone !== "primary";
  return (
    <div
      className={`desktop-modal confirm-modal${isOpen ? " is-open" : ""}${danger ? " is-danger" : ""}`}
    >
      <div className="desktop-modal-backdrop" onClick={onCancel} />
      <section
        className="desktop-modal-card confirm-modal-card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-message"
      >
        <div className="confirm-modal-body">
          <div className="confirm-modal-icon" aria-hidden="true">
            <CircleAlert className="desktop-icon" />
          </div>
          <div className="confirm-modal-text">
            <div id="confirm-title" className="confirm-modal-title">
              {options.title}
            </div>
            <div id="confirm-message" className="confirm-modal-message">
              {options.message}
            </div>
          </div>
        </div>
        <div className="confirm-modal-actions">
          <button className="new-session-secondary" type="button" onClick={onCancel}>
            {options.cancelText ?? "取消"}
          </button>
          <button
            className="confirm-modal-primary"
            type="button"
            onClick={onConfirm}
            autoFocus
          >
            {options.confirmText ?? "确认"}
          </button>
        </div>
      </section>
    </div>
  );
}
