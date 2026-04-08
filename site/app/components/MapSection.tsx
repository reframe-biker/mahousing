"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import type { TownRecord } from "@/src/types/town";
import { type ActiveDimension, DIMENSION_LABELS } from "./Map";

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
  backgroundColor: "#ffffff",
  border: "1px solid #e0ddd8",
  color: "#1a1816",
  fontSize: "14px",
  borderRadius: "6px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
  outline: "none",
};

export default function MapSection({ towns }: { towns: TownRecord[] }) {
  const [activeDimension, setActiveDimension] = useState<ActiveDimension>("composite");

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
          onChange={(e) => setActiveDimension(e.target.value as ActiveDimension)}
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
