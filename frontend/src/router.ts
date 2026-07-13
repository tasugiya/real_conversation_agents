import { useEffect, useState } from "react";

// Minimal pushState router. No third-party dependency -- the app only has a
// handful of flat routes, so history.pushState + a popstate listener is
// enough to get a real URL per screen, working back/forward, and reload
// safety (see storage.ts for what makes reload actually work).
export type Route = "/" | "/setup" | "/session" | "/review" | "/reviews";

const KNOWN_ROUTES: Route[] = ["/", "/setup", "/session", "/review", "/reviews"];

function normalize(pathname: string): Route {
  return (KNOWN_ROUTES as string[]).includes(pathname) ? (pathname as Route) : "/";
}

export function navigate(path: Route, options?: { replace?: boolean }): void {
  if (window.location.pathname === path) return;
  if (options?.replace) window.history.replaceState({}, "", path);
  else window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => normalize(window.location.pathname));
  useEffect(() => {
    const onPopState = () => setRoute(normalize(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  return route;
}
