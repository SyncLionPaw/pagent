import { useEffect, useState } from "react";

/**
 * 对标 desktop 各 modal 的开合动画：先挂载再下一帧加 is-open，关闭时先撤 is-open 再延时卸载。
 * 返回 mounted 决定是否渲染 DOM，isOpen 决定 is-open 类。
 */
export function useModalTransition(open: boolean, duration = 140): {
  mounted: boolean;
  isOpen: boolean;
} {
  const [mounted, setMounted] = useState(open);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      const frame = window.requestAnimationFrame(() => setIsOpen(true));
      return () => window.cancelAnimationFrame(frame);
    }
    setIsOpen(false);
    const timer = window.setTimeout(() => setMounted(false), duration);
    return () => window.clearTimeout(timer);
  }, [open, duration]);

  return { mounted, isOpen };
}
