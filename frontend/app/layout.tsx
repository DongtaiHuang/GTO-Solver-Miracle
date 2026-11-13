import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "../components/AppShell";

export const metadata: Metadata = {
  title: "MIRACLE · Poker Strategy Lab",
  icons: { icon: "/brand/orange-spade.png" },
  description: "Study poker ranges and opponent models with transparent strategy sources",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><AppShell>{children}</AppShell></body></html>;
}
