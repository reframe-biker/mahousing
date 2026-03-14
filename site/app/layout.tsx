import type { Metadata } from "next";
import { DM_Sans, DM_Mono } from "next/font/google";
import "./globals.css";

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
            <div className="flex items-center gap-4">
              <a
                href="/mbta"
                style={{
                  color: "#f0ede8",
                  fontSize: "14px",
                  fontWeight: 500,
                  textDecoration: "none",
                  opacity: 0.85,
                }}
              >
                MBTA tracker
              </a>
            <a
              href="https://github.com/reframe-biker/mahousing"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub repository"
              className="nav-icon-link"
            >
              <svg
                className="w-5 h-5"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                />
              </svg>
            </a>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
