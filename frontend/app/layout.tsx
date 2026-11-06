import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Poker Strategy Lab",
  description: "Deterministic No-Limit Texas Hold’em engine foundation",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
