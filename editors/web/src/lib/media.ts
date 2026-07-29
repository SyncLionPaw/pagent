import { useEffect, useState } from "react";

export const MOBILE_MEDIA_QUERY = "(max-width: 768px)";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const media = window.matchMedia(query);
    const sync = () => setMatches(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, [query]);

  return matches;
}

/** Keep the composer above the mobile browser chrome and virtual keyboard. */
export function useVisualViewportInset(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) {
      document.documentElement.style.removeProperty("--vv-bottom-inset");
      return;
    }
    const viewport = window.visualViewport;
    if (!viewport) {
      return;
    }
    const sync = () => {
      const inset = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
      document.documentElement.style.setProperty("--vv-bottom-inset", `${inset}px`);
    };
    sync();
    viewport.addEventListener("resize", sync);
    viewport.addEventListener("scroll", sync);
    window.addEventListener("orientationchange", sync);
    return () => {
      viewport.removeEventListener("resize", sync);
      viewport.removeEventListener("scroll", sync);
      window.removeEventListener("orientationchange", sync);
      document.documentElement.style.removeProperty("--vv-bottom-inset");
    };
  }, [enabled]);
}
