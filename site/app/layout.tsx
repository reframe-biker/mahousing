import type { Metadata } from "next";
import { DM_Sans, DM_Mono } from "next/font/google";
import "./globals.css";
import GoatCounter from "@/app/components/GoatCounter";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-dm-sans",
  display: "swap",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-dm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MA Housing Report Card",
  description:
    "Grades for every Massachusetts municipality on housing policy, derived from public data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${dmSans.variable} ${dmMono.variable}`}>
      <body className="antialiased">
        {/* Thin accent bar — NYT-style category color line */}
        <div
          aria-hidden="true"
          style={{ height: "2px", backgroundColor: "#e8e0d4" }}
        />
        <nav
          style={{
            backgroundColor: "#1c1916",
            borderBottom: "1px solid #2e2a26",
          }}
        >
          <div className="max-w-screen-xl mx-auto px-4 h-12 flex items-center justify-between">
            <a href="/" className="nav-brand">
              MA Housing Report Card
            </a>
            <div className="flex items-center gap-5">
              <a href="/mbta" className="nav-icon-link" style={{ fontSize: "14px", fontWeight: 500 }}>
                MBTA tracker
              </a>
              <a href="/methodology" className="nav-icon-link" style={{ fontSize: "14px", fontWeight: 500 }}>
                Methodology
              </a>
            </div>
          </div>
        </nav>
        {children}
        <GoatCounter />
      </body>
    </html>
  );
}
