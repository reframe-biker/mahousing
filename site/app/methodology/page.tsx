import fs from "fs";
import type { Metadata } from "next";
import { remark } from "remark";
import remarkHtml from "remark-html";
import { getRepoRoot } from "@/src/lib/paths";

export const metadata: Metadata = {
  title: "Methodology — MA Housing Report Card",
  description:
    "How MA Housing Report Card grades every Massachusetts municipality on housing policy. Data sources, scoring formulas, and grading rubrics.",
};

async function getMethodologyHtml(): Promise<string> {
  const filePath = getRepoRoot("METHODOLOGY.md");
  const raw = fs.readFileSync(filePath, "utf-8");
  const result = await remark().use(remarkHtml).process(raw);
  return result.toString();
}

export default async function MethodologyPage() {
  const html = await getMethodologyHtml();

  return (
    <div style={{ backgroundColor: "var(--bg-primary)", minHeight: "100vh" }}>
      {/* Back link */}
      <div style={{ maxWidth: "720px", margin: "0 auto", padding: "2rem 1.5rem 0" }}>
        <a
          href="/"
          className="text-sm inline-flex items-center gap-1 transition-colors"
          style={{ color: "var(--accent)" }}
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Statewide map
        </a>
      </div>

      {/* Markdown content */}
      <div
        className="methodology-content"
        dangerouslySetInnerHTML={{ __html: html }}
      />

      {/* Footer */}
      <footer
        className="pt-6 text-xs text-center"
        style={{
          borderTop: "1px solid var(--border)",
          color: "var(--text-muted)",
        }}
      >
        <span>Built with public data · Updated weekly</span>
      </footer>
    </div>
  );
}
