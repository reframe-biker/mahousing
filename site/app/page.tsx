import dynamic from "next/dynamic";
import fs from "fs";
import path from "path";
import type { TownRecord } from "@/src/types/town";

// Leaflet requires a browser environment — load with SSR disabled
const MapClient = dynamic(() => import("@/app/components/Map"), {
  ssr: false,
  loading: () => (
    <div
      className="w-full h-full flex items-center justify-center"
      style={{ backgroundColor: "var(--bg-primary)" }}
    >
      <p className="text-sm font-mono" style={{ color: "var(--text-muted)" }}>
        Loading map…
      </p>
    </div>
  ),
});

function loadStatewideData(): TownRecord[] {
  const dataPath = path.join(process.cwd(), "..", "data", "statewide.json");
  const raw = fs.readFileSync(dataPath, "utf-8");
  return JSON.parse(raw) as TownRecord[];
}

export default function HomePage() {
  const towns = loadStatewideData();
  const updatedAt = towns[0]?.updated_at ?? "unknown";

  return (
    // 3rem nav + 3px accent bar
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
        <p
          className="text-xs font-mono"
          style={{ color: "var(--text-muted)" }}
        >
          Data as of {updatedAt}
        </p>
      </div>

      {/* Map fills remaining viewport */}
      <div className="flex-1 min-h-0 relative">
        <MapClient towns={towns} />
      </div>
    </div>
  );
}
