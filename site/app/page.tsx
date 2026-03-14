import dynamic from "next/dynamic";
import fs from "fs";
import path from "path";
import type { TownRecord } from "@/src/types/town";

// Leaflet requires a browser environment — load with SSR disabled
const MapClient = dynamic(() => import("@/app/components/Map"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-gray-50">
      <p className="text-gray-400 text-sm">Loading map…</p>
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
    <div className="flex flex-col" style={{ height: "calc(100vh - 3rem)" }}>
      {/* Page header */}
      <div className="px-4 py-3 border-b border-gray-100 flex-shrink-0 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-gray-600">
          Every Massachusetts municipality graded on housing policy using public data.{" "}
          <span className="text-gray-400">Click a town for the full breakdown.</span>
        </p>
        <p className="text-xs text-gray-400">Data as of {updatedAt}</p>
      </div>

      {/* Map fills remaining viewport */}
      <div className="flex-1 min-h-0 relative">
        <MapClient towns={towns} />
      </div>
    </div>
  );
}
