"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { TownRecord } from "@/src/types/town";
import { type ActiveDimension, DIMENSION_LABELS, isTouchDevice } from "./Map";

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
  const [search, setSearch] = useState("");

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
      {/* Controls — search + dimension selector in one flexbox row */}
      <div
        className="absolute pointer-events-none flex flex-wrap gap-2"
        style={{ top: "12px", left: isTouchDevice() ? "12px" : "60px", right: "12px", zIndex: 1001 }}
      >
        <input
          type="search"
          placeholder="Search municipality…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pointer-events-auto px-3 py-2 w-52"
          style={controlStyle}
          aria-label="Search municipality"
        />
        <select
          className="pointer-events-auto px-3 py-2 flex-shrink-0"
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
      <MapClient towns={towns} dimension={activeDimension} search={search} />
    </div>
  );
}
