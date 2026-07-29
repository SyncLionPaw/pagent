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

/** Pin the mobile shell to the visible viewport (Safari bottom bar / keyboard). */
export function useMobileViewport(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) {
      document.documentElement.style.removeProperty("--app-height");
      document.documentElement.style.removeProperty("--vv-offset-top");
      return;
    }
    const viewport = window.visualViewport;
    const sync = () => {
      const height = viewport?.height ?? window.innerHeight;
      const offsetTop = viewport?.offsetTop ?? 0;
      document.documentElement.style.setProperty("--app-height", `${height}px`);
      document.documentElement.style.setProperty("--vv-offset-top", `${offsetTop}px`);
      if (window.scrollY !== 0) {
        window.scrollTo(0, 0);
      }
    };
    sync();
    viewport?.addEventListener("resize", sync);
    viewport?.addEventListener("scroll", sync);
    window.addEventListener("resize", sync);
    window.addEventListener("orientationchange", sync);
    return () => {
      viewport?.removeEventListener("resize", sync);
      viewport?.removeEventListener("scroll", sync);
      window.removeEventListener("resize", sync);
      window.removeEventListener("orientationchange", sync);
      document.documentElement.style.removeProperty("--app-height");
      document.documentElement.style.removeProperty("--vv-offset-top");
    };
  }, [enabled]);
}
