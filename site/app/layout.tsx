import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
