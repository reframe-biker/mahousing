"use client";

import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import type { TownRecord } from "@/src/types/town";
import { type ActiveDimension, DIMENSION_LABELS } from "./Map";

const VALID_DIMENSIONS: ActiveDimension[] = ["composite", "zoning", "legislators", "production", "affordability", "mbta"];

function isActiveDimension(value: string | null): value is ActiveDimension {
  return VALID_DIMENSIONS.includes(value as ActiveDimension);
}

// Leaflet requires a browser environment — load with SSR disabled
const MapClient = dynamic(() => import("./Map"), {
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

const controlStyle: React.CSSProperties = {
  backgroundColor: "var(--bg-card)",
  border: "1px solid var(--border)",
  color: "var(--text-primary)",
  fontSize: "14px",
  borderRadius: "6px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
  outline: "none",
};

export default function MapSection({ towns }: { towns: TownRecord[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const rawDim = searchParams.get("dim");
  const activeDimension: ActiveDimension = isActiveDimension(rawDim)
    ? rawDim
    : isActiveDimension(
        typeof window !== "undefined"
          ? sessionStorage.getItem("mapDimension")
          : null
      )
    ? (sessionStorage.getItem("mapDimension") as ActiveDimension)
    : "composite";

  return (
    <div className="relative w-full h-full">
      {/* Dimension selector — overlaid in the same top-left control area as the old grade filter */}
      <div
        className="absolute pointer-events-none"
        style={{ top: "12px", left: "276px", zIndex: 1001 }}
      >
        <select
          className="pointer-events-auto px-3 py-2"
          style={controlStyle}
          value={activeDimension}
          onChange={(e) => {
            sessionStorage.setItem("mapDimension", e.target.value);
            router.push(`?dim=${e.target.value}`, { scroll: false });
          }}
          aria-label="Select grading dimension"
        >
          {(Object.entries(DIMENSION_LABELS) as [ActiveDimension, string][]).map(
            ([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            )
          )}
        </select>
      </div>
      <MapClient towns={towns} dimension={activeDimension} />
    </div>
  );
}
