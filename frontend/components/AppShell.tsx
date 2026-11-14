"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const links = [{ href: "/", title: "Study", icon: "◈", note: "Ranges & models" },
    { href: "/training", title: "Training Center", icon: "◎", note: "Decision practice" },
    { href: "/trainer", title: "Trainer", icon: "♠", note: "Practice full hands" },
    { href: "/analyzer", title: "Hand Analyzer", icon: "≡", note: "Review workspace" },
    { href: "/account", title: "Player Account", icon: "○", note: "Saved records" }];
  return <div className="app-shell"><a className="skip-content" href="#workspace-content">Skip to workspace</a><aside className="app-sidebar">
    <Link href="/" className="brand-lockup"><img src="/brand/orange-spade.png" width="36" height="36" alt="" />
      <span>MIRACLE<small>POKER STRATEGY LAB</small></span></Link>
    <p className="nav-caption">WORKSPACE</p>
    <nav aria-label="Main navigation">{links.filter(link=>link.href!=="/account" || process.env.NEXT_PUBLIC_GUEST_DEMO!=="true").map(link => <Link key={link.href} href={link.href}
      aria-current={path === link.href ? "page" : undefined}>
      <span className="nav-icon" aria-hidden="true">{link.icon}</span><span>{link.title}<small>{link.note}</small></span>
    </Link>)}</nav>
    <div className="sidebar-note"><span className="status-dot" /> RESEARCH BUILD
      <p>Study the assumptions.<br />Know the source.</p><span className="availability-tag">Coverage requires an exact match</span></div>
  </aside><div className="app-content" id="workspace-content" tabIndex={-1}>{children}</div></div>;
}
