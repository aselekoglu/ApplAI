import { NavLink, useLocation } from "react-router-dom";
import type { PropsWithChildren } from "react";

export function AppLayout({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const wideMasters = pathname.startsWith("/masters");
  return (
    <div className={`layout${wideMasters ? " layout--wide" : ""}`}>
      <header className="topbar">
        <div>
          <h1>ApplAI</h1>
          <p className="muted">Master CV, tailoring, and runs — data lives under docs/</p>
        </div>
        <nav className="navlinks">
          <NavLink to="/masters">Masters</NavLink>
          <NavLink to="/tailoring">Tailoring</NavLink>
          <NavLink to="/runs">Runs</NavLink>
        </nav>
      </header>
      <main className="page">{children}</main>
    </div>
  );
}
