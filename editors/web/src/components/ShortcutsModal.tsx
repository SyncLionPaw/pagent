import { Activity, ArrowLeft, ChevronRight, Folder, HardDrive, X } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useModalTransition } from "../lib/useModalTransition";

type Props = {
  open: boolean;
  onClose: () => void;
};

type Slide = {
  title: string;
  body: ReactNode;
};

const SLIDES: Slide[] = [
  {
    title: "Thread",
    body: "每次对话落在一条 Thread 上：消息历史、配置与工作区都绑在一起。",
  },
  {
    title: "Project",
    body: "Thread 绑定你的 Project（宿主目录）。右侧「项目」看的就是这里。",
  },
  {
    title: "Agent Computer",
    body: "同时绑定一台 Agent Computer（沙箱）。右侧「沙箱」看的就是它的工作区。",
  },
  {
    title: "Artifacts",
    body: (
      <>
        Artifacts 在 Project 里（<code>project/artifacts/</code>）。
        <code>copy_from_host</code> 从项目拉进沙箱，
        <code>copy_to_host</code> 交回该目录。
      </>
    ),
  },
];

const SHORTCUTS: Array<{ label: string; keyCap: string }> = [
  { label: "收缩左侧", keyCap: "L" },
  { label: "收缩右侧", keyCap: "R" },
  { label: "打开本面板", keyCap: "K" },
];

/** 对标 desktop shortcuts-modal + 心智模型轮播（playMentalModelDemo / applyMentalCarousel）。 */
export function ShortcutsModal({ open, onClose }: Props) {
  const { mounted, isOpen } = useModalTransition(open);
  const [slideIndex, setSlideIndex] = useState(0);
  const modelRef = useRef<HTMLElement>(null);

  const layoutBridge = useCallback(() => {
    const model = modelRef.current;
    if (!model) {
      return;
    }
    const stage = model.querySelector<HTMLElement>("[data-mental-stage]");
    const artifacts = model.querySelector<HTMLElement>(".mental-nested-artifacts");
    const agent = model.querySelector<HTMLElement>(".mental-node-agent");
    const bridge = model.querySelector<HTMLElement>(".mental-bridge");
    if (!stage || !artifacts || !agent || !bridge) {
      return;
    }
    const stageRect = stage.getBoundingClientRect();
    const artifactsRect = artifacts.getBoundingClientRect();
    const agentRect = agent.getBoundingClientRect();
    if (stageRect.width < 1 || artifactsRect.width < 1 || agentRect.width < 1) {
      return;
    }
    const left = Math.max(0, artifactsRect.right - stageRect.left);
    const right = Math.max(0, stageRect.right - agentRect.left);
    const top = (artifactsRect.top + artifactsRect.bottom) / 2 - stageRect.top - 7;
    bridge.style.left = `${left}px`;
    bridge.style.right = `${right}px`;
    bridge.style.top = `${top}px`;
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    setSlideIndex(0);
    const model = modelRef.current;
    model?.classList.remove("is-playing");
    void model?.offsetWidth;
    model?.classList.add("is-playing");
    const frame = window.requestAnimationFrame(() => layoutBridge());
    const timer = window.setTimeout(layoutBridge, 1800);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
      model?.classList.remove("is-playing");
    };
  }, [open, layoutBridge]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onResize = () => layoutBridge();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [open, layoutBridge]);

  if (!mounted) {
    return null;
  }

  const total = SLIDES.length;
  const goTo = (index: number) => setSlideIndex(((index % total) + total) % total);

  return (
    <div className={`desktop-modal${isOpen ? " is-open" : ""}`}>
      <div className="desktop-modal-backdrop" onClick={onClose} />
      <section
        className="desktop-modal-card shortcuts-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
      >
        <div className="desktop-modal-header">
          <div id="shortcuts-title" className="desktop-modal-title">
            快捷键与心智模型
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
        <div className="desktop-modal-body shortcuts-modal-body">
          <div className="shortcuts-list">
            {SHORTCUTS.map((item) => (
              <div className="shortcut-item" key={item.keyCap}>
                <span className="shortcut-label">{item.label}</span>
                <div className="shortcut-keys">
                  <kbd className="key-modifier">
                    <span className="key-icon">⌘</span>
                    <span className="key-label">Command</span>
                  </kbd>
                  <kbd>{item.keyCap}</kbd>
                </div>
              </div>
            ))}
          </div>
          <section className="mental-model" ref={modelRef} aria-label="心智模型演示">
            <div className="mental-model-heading">
              <div className="mental-model-title">一条 Thread，两处绑定</div>
            </div>
            <div className="mental-carousel">
              <button
                type="button"
                className="mental-carousel-nav"
                title="上一条"
                aria-label="上一条"
                disabled={slideIndex === 0}
                onClick={() => goTo(slideIndex - 1)}
              >
                <ArrowLeft className="desktop-icon" aria-hidden="true" />
              </button>
              <div className="mental-carousel-viewport">
                <div
                  className="mental-carousel-track"
                  style={{ transform: `translateX(-${slideIndex * 100}%)` }}
                >
                  {SLIDES.map((slide) => (
                    <div className="mental-carousel-slide" key={slide.title}>
                      <div className="mental-carousel-slide-title">{slide.title}</div>
                      <div className="mental-carousel-slide-body">{slide.body}</div>
                    </div>
                  ))}
                </div>
              </div>
              <button
                type="button"
                className="mental-carousel-nav"
                title="下一条"
                aria-label="下一条"
                disabled={slideIndex === total - 1}
                onClick={() => goTo(slideIndex + 1)}
              >
                <ChevronRight className="desktop-icon" aria-hidden="true" />
              </button>
            </div>
            <div className="mental-carousel-dots" role="tablist" aria-label="说明页">
              {SLIDES.map((slide, index) => (
                <button
                  key={slide.title}
                  type="button"
                  className={`mental-carousel-dot${index === slideIndex ? " active" : ""}`}
                  role="tab"
                  aria-label={`第 ${index + 1} 页`}
                  aria-selected={index === slideIndex}
                  onClick={() => goTo(index)}
                />
              ))}
            </div>
            <div className="mental-model-stage" data-mental-stage>
              <svg className="mental-model-links" viewBox="0 0 360 120" aria-hidden="true">
                <path
                  className="mental-link mental-link-project"
                  d="M180 28 C120 28, 90 52, 78 78"
                  fill="none"
                  strokeLinecap="round"
                />
                <path
                  className="mental-link mental-link-agent"
                  d="M180 28 C240 28, 270 52, 288 78"
                  fill="none"
                  strokeLinecap="round"
                />
                <circle className="mental-packet mental-packet-project" r="3.5" />
                <circle className="mental-packet mental-packet-agent" r="3.5" />
              </svg>
              <div className="mental-bridge" aria-hidden="true">
                <span className="mental-bridge-line" />
                <span className="mental-bridge-packet mental-bridge-packet-out" />
                <span className="mental-bridge-packet mental-bridge-packet-in" />
              </div>
              <div className="mental-node mental-node-thread">
                <span className="mental-node-icon">
                  <Activity className="desktop-icon" aria-hidden="true" />
                </span>
                <span className="mental-node-label">Thread</span>
                <span className="mental-node-sub">会话</span>
              </div>
              <div className="mental-node mental-node-project">
                <span className="mental-node-icon">
                  <Folder className="desktop-icon" aria-hidden="true" />
                </span>
                <span className="mental-node-label">Project</span>
                <span className="mental-node-sub">你的项目目录</span>
                <div className="mental-nested mental-nested-artifacts">
                  <span className="mental-nested-label">artifacts/</span>
                  <span className="mental-nested-methods">
                    <span>copy_from_host</span>
                    <span>copy_to_host</span>
                  </span>
                </div>
              </div>
              <div className="mental-node mental-node-agent">
                <span className="mental-node-icon">
                  <HardDrive className="desktop-icon" aria-hidden="true" />
                </span>
                <span className="mental-node-label">Agent Computer</span>
                <span className="mental-node-sub">沙箱工作区</span>
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
