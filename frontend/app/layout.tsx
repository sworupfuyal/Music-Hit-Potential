import type { Metadata } from "next";

import { AppShell } from "@/components/shell/AppShell";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "HitLab — Music Hit Potential",
  description: "Predict hit potential from song features using your trained pipeline.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-canvas text-ink antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
