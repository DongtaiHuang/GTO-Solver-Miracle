"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const links = [{ href: "/", title: "Study", icon: "◈", note: "Ranges & models" },
    { href: "/trainer", title: "Trainer", icon: "♠", note: "Practice full hands" },
    { href: "/hand-analyzer", title: "Hand Analyzer", icon: "≡", note: "Review workspace" }];
  return <div className="app-shell"><aside className="app-sidebar">
    <Link href="/" className="brand-lockup"><span className="brand-mark">M</span>
      <span>MIRACLE<small>POKER STRATEGY LAB</small></span></Link>
    <p className="nav-caption">WORKSPACE</p>
    <nav aria-label="Main navigation">{links.map(link => <Link key={link.href} href={link.href}
      aria-current={path === link.href ? "page" : undefined}>
      <span className="nav-icon">{link.icon}</span><span>{link.title}<small>{link.note}</small></span>
    </Link>)}</nav>
    <div className="sidebar-note"><span className="status-dot" /> RESEARCH BUILD
      <p>Study the assumptions.<br />Know the source.</p><span className="availability-tag">No solver dataset connected</span></div>
  </aside><div className="app-content">{children}</div></div>;
}
