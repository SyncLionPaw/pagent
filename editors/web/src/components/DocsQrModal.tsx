import * as QRCode from "qrcode";
import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { DOCUMENTATION_URL } from "../lib/format";
import { useModalTransition } from "../lib/useModalTransition";

type Props = {
  open: boolean;
  onClose: () => void;
};

/** 对标 desktop openDocsQrModal + docs-qr.ts：canvas 渲染文档站二维码，供微信扫码。 */
export function DocsQrModal({ open, onClose }: Props) {
  const { mounted, isOpen } = useModalTransition(open);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    void QRCode.toCanvas(canvas, DOCUMENTATION_URL, {
      width: 220,
      margin: 1,
      errorCorrectionLevel: "M",
      color: { dark: "#1a1a1a", light: "#ffffff" },
    }).catch(() => {
      const ctx = canvas.getContext("2d");
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    });
  }, [open, mounted]);

  if (!mounted) {
    return null;
  }
  return (
    <div className={`desktop-modal${isOpen ? " is-open" : ""}`}>
      <div className="desktop-modal-backdrop" onClick={onClose} />
      <section
        className="desktop-modal-card docs-qr-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="docs-qr-title"
      >
        <div className="desktop-modal-header">
          <div id="docs-qr-title" className="desktop-modal-title">
            扫码打开文档
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
        <div className="desktop-modal-body docs-qr-body">
          <div className="docs-qr-frame">
            <canvas
              ref={canvasRef}
              width={220}
              height={220}
              aria-label="pagent 文档站二维码"
            />
          </div>
          <p className="docs-qr-hint">微信扫一扫，在手机上阅读 pagent 文档</p>
          <button
            className="new-session-primary docs-qr-open"
            type="button"
            onClick={() => window.open(DOCUMENTATION_URL, "_blank", "noreferrer")}
          >
            在浏览器中打开
          </button>
        </div>
      </section>
    </div>
  );
}
