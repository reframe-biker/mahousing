import fs from "fs";
import path from "path";
import type { Metadata } from "next";
import type { TownRecord } from "@/src/types/town";
import MbtaClient from "./MbtaClient";

export const metadata: Metadata = {
  title: "MBTA Communities Tracker — MA Housing Report Card",
  description:
    "Track compliance with the MBTA Communities Act for all subject Massachusetts municipalities. Updated from DHCD compliance data.",
};

function loadStatewideData(): TownRecord[] {
  const dataPath = path.join(process.cwd(), "..", "data", "statewide.json");
  return JSON.parse(fs.readFileSync(dataPath, "utf-8")) as TownRecord[];
}

export default function MbtaPage() {
  const allTowns = loadStatewideData();

  // Include all towns with a known MBTA status (subject + exempt)
  // Towns with mbta_status === null have not yet been scraped — exclude them.
  const mbtaTowns = allTowns.filter((t) => t.mbta_status !== null);
  const updatedAt = allTowns[0]?.updated_at ?? "unknown";

  return (
    <main
      className="max-w-screen-lg mx-auto px-4 py-8"
      style={{ backgroundColor: "var(--bg-primary)" }}
    >
      {/* Header */}
      <div className="mb-8">
        <div className="mb-2">
          <a
            href="/"
            className="text-sm inline-flex items-center gap-1"
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

        <h1
          className="text-3xl mb-3"
          style={{ fontWeight: 600, color: "var(--text-primary)" }}
        >
          MBTA Communities Act Tracker
        </h1>
        <p
          className="text-sm leading-relaxed max-w-2xl"
          style={{ color: "var(--text-secondary)" }}
        >
          The MBTA Communities Act requires 177 Massachusetts municipalities
          served by the MBTA to create at least one zoning district near transit
          that allows multifamily housing by right. Towns that fail to comply
          lose access to certain state grant programs, and the Attorney General
          is actively enforcing the law. The table below shows current
          compliance status for all subject municipalities, sourced directly
          from the MA Department of Housing and Community Development (DHCD).
        </p>
        <p
          className="mt-3 text-xs"
          style={{
            color: "var(--text-muted)",
            fontFamily: "var(--font-dm-sans), sans-serif",
            fontSize: "13px",
          }}
        >
          Compliance data from EOHLC Compliance Status Sheet, updated March 13,
          2026. Replace data/mbta_compliance_source.csv to update.
        </p>
      </div>

      <MbtaClient towns={mbtaTowns} updatedAt={updatedAt} />
    </main>
  );
}
