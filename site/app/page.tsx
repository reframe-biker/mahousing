import fs from "fs";
import type { TownRecord } from "@/src/types/town";
import { getDataPath } from "@/src/lib/paths";
import MapSection from "@/app/components/MapSection";

function loadStatewideData(): TownRecord[] {
  return JSON.parse(fs.readFileSync(getDataPath("statewide.json"), "utf-8")) as TownRecord[];
}

export default function HomePage() {
  const towns = loadStatewideData();
  const updatedAt = towns[0]?.updated_at ?? "unknown";

  return (
    // 3rem nav + 3px accent bar; footer is 2.5rem
    <div className="flex flex-col" style={{ height: "calc(100vh - 3rem - 3px)" }}>
      {/* Page header */}
      <div
        className="px-4 py-3 flex-shrink-0 flex flex-wrap items-baseline justify-between gap-2"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Every Massachusetts municipality graded on housing policy using public data.{" "}
          <span style={{ color: "var(--accent)" }}>Click a town for the full breakdown.</span>
        </p>
      </div>

      {/* Map fills remaining viewport */}
      <div className="flex-1 min-h-0 relative">
        <MapSection towns={towns} />
      </div>

      {/* Footer */}
      <div
        className="flex-shrink-0 px-4 flex items-center justify-center text-xs"
        style={{
          borderTop: "1px solid var(--border)",
          backgroundColor: "var(--bg-secondary)",
          color: "var(--text-muted)",
          height: "2.5rem",
        }}
      >
        <span>Built with public data · Data as of {updatedAt} · Updated weekly</span>
      </div>
    </div>
  );
}
