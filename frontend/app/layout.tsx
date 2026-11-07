import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Poker Strategy Lab",
  description: "Play six-player No-Limit Texas Hold’em against heuristic practice opponents",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
