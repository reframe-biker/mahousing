"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { TownRecord, Grade } from "@/src/types/town";

// Grade color palette (matches gradeConfig in GradeBadge)
const GRADE_COLOR: Record<NonNullable<Grade> | "null", string> = {
  A: "#2d6a4f",
  B: "#74c69d",
  C: "#ffd166",
  D: "#ef9a00",
  F: "#e63946",
  null: "#d0d0d0",
};

// Local static file committed to site/public/
const GEOJSON_URL = "/ma-towns.geojson";

function getGeoid(props: Record<string, unknown>): string | null {
  const v = props["GEOID"];
  return typeof v === "string" ? v.trim() : null;
}

// Build a lookup index from FIPS/GEOID → TownRecord
function buildTownIndex(towns: TownRecord[]): Record<string, TownRecord> {
  const index: Record<string, TownRecord> = {};
  for (const t of towns) {
    index[t.fips] = t;
  }
  return index;
}

interface Props {
  towns: TownRecord[];
}

export default function Map({ towns }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMapRef = useRef<import("leaflet").Map | null>(null);
  const layerRef = useRef<import("leaflet").GeoJSON | null>(null);
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [filterGrade, setFilterGrade] = useState<Grade | "all">("all");
  const [geoError, setGeoError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const townIndex = useRef(buildTownIndex(towns));

  // Initialize Leaflet map after mount
  useEffect(() => {
    if (!mapRef.current || leafletMapRef.current) return;

    // Dynamic import keeps Leaflet out of SSR bundle
    let cancelled = false;

    (async () => {
      const L = (await import("leaflet")).default;

      if (cancelled || !mapRef.current) return;

      const map = L.map(mapRef.current, {
        center: [42.15, -71.65],
        zoom: 8,
        zoomControl: true,
      });
      leafletMapRef.current = map;

      // Base tile layer (CartoDB Positron — clean, low-contrast)
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
          subdomains: "abcd",
          maxZoom: 19,
        }
      ).addTo(map);

      // Tooltip
      const tooltip = L.tooltip({
        permanent: false,
        direction: "top",
        className: "ma-tooltip",
      });

      // Load local GeoJSON from public/
      let geojsonData: GeoJSON.FeatureCollection;
      try {
        const res = await fetch(GEOJSON_URL);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        geojsonData = await res.json();
      } catch (err) {
        setGeoError("Could not load MA town boundaries. Map data unavailable.");
        setLoading(false);
        console.error("GeoJSON load error:", err);
        return;
      }

      if (cancelled) return;

      function styleFeature(
        feature: GeoJSON.Feature | undefined,
        grade: Grade
      ) {
        const color = GRADE_COLOR[grade ?? "null"];
        return {
          fillColor: color,
          fillOpacity: 0.75,
          color: "#ffffff",
          weight: 0.8,
          opacity: 1,
        };
      }

      function getTownByProps(
        props: Record<string, unknown>
      ): TownRecord | undefined {
        const geoid = getGeoid(props);
        return geoid ? townIndex.current[geoid] : undefined;
      }

      const geoLayer = L.geoJSON(geojsonData, {
        style: (feature) => {
          const props = (feature?.properties ?? {}) as Record<string, unknown>;
          const grade = getTownByProps(props)?.grades?.composite ?? null;
          return styleFeature(feature, grade);
        },
        onEachFeature(feature, layer) {
          const props = (feature.properties ?? {}) as Record<string, unknown>;
          const town = getTownByProps(props);
          const townName = town?.name ?? (props["census_name"] as string | undefined) ?? "Unknown";
          const grade = town?.grades?.composite ?? null;
          const fips = town?.fips ?? null;

          layer.on({
            mouseover(e) {
              const target = e.target as import("leaflet").Path;
              target.setStyle({ fillOpacity: 0.95, weight: 2, color: "#333" });
              tooltip
                .setLatLng(e.latlng)
                .setContent(
                  `<strong>${townName}</strong><br/>Composite: <strong>${grade ?? "No data"}</strong>`
                )
                .addTo(map);
            },
            mouseout(e) {
              geoLayer.resetStyle(e.target as import("leaflet").Path);
              tooltip.remove();
            },
            click() {
              if (fips) router.push(`/town/${fips}`);
            },
          });
        },
      });

      geoLayer.addTo(map);
      layerRef.current = geoLayer;

      // Fit map to MA bounds
      try {
        const bounds = geoLayer.getBounds();
        if (bounds.isValid()) map.fitBounds(bounds, { padding: [10, 10] });
      } catch {
        // keep default center/zoom
      }

      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Apply grade filter when filterGrade changes
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    layer.eachLayer((l) => {
      const gl = l as import("leaflet").Path & {
        feature?: GeoJSON.Feature;
      };
      const props = (gl.feature?.properties ?? {}) as Record<string, unknown>;
      const geoid = getGeoid(props);
      const grade = (geoid ? townIndex.current[geoid] : undefined)?.grades?.composite ?? null;

      const visible =
        filterGrade === "all" || grade === filterGrade;
      gl.setStyle({ fillOpacity: visible ? 0.75 : 0.05, opacity: visible ? 1 : 0.2 });
    });
  }, [filterGrade]);

  // Search: fly to matched town
  function handleSearch(query: string) {
    setSearch(query);
    if (!query.trim() || !leafletMapRef.current || !layerRef.current) return;

    const q = query.toLowerCase().trim();
    // Use an array so TypeScript doesn't narrow the closure assignment to never
    const matchedLayers: (import("leaflet").Layer & { feature?: GeoJSON.Feature })[] = [];

    layerRef.current.eachLayer((l) => {
      if (matchedLayers.length > 0) return;
      const gl = l as import("leaflet").Layer & { feature?: GeoJSON.Feature };
      const props = (gl.feature?.properties ?? {}) as Record<string, unknown>;
      const geoid = getGeoid(props);
      const town = geoid ? townIndex.current[geoid] : undefined;
      const displayName = town?.name ?? (props["census_name"] as string | undefined) ?? "";
      if (displayName.toLowerCase().includes(q)) {
        matchedLayers.push(gl);
      }
    });

    const matchedLayer = matchedLayers[0];
    if (matchedLayer && leafletMapRef.current) {
      try {
        const asGeo = matchedLayer as unknown as { getBounds: () => import("leaflet").LatLngBounds };
        const bounds = asGeo.getBounds();
        if (bounds?.isValid()) {
          leafletMapRef.current.flyToBounds(bounds, { padding: [40, 40], duration: 0.8 });
        }
      } catch {
        // Polygon may not have getBounds
      }
      (matchedLayer as unknown as import("leaflet").Path).setStyle({
        color: "#1d3461",
        weight: 3,
      });
      setTimeout(() => {
        layerRef.current?.resetStyle(matchedLayer as unknown as import("leaflet").Path);
      }, 2500);
    }
  }

  const gradeOptions: Array<{ value: Grade | "all"; label: string }> = [
    { value: "all", label: "All grades" },
    { value: "A", label: "A — Excellent" },
    { value: "B", label: "B — Good" },
    { value: "C", label: "C — Below average" },
    { value: "D", label: "D — Poor" },
    { value: "F", label: "F — Failing" },
    { value: null, label: "No data" },
  ];

  return (
    <div className="relative w-full h-full">
      {/* Controls bar */}
      <div className="absolute top-3 left-3 right-3 z-[1000] flex flex-wrap gap-2 pointer-events-none">
        <input
          type="search"
          placeholder="Search municipality…"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="pointer-events-auto px-3 py-2 text-sm bg-white border border-gray-300 rounded shadow-sm w-52 focus:outline-none focus:ring-1 focus:ring-gray-400"
          aria-label="Search municipality"
        />
        <select
          value={filterGrade === null ? "null" : filterGrade}
          onChange={(e) => {
            const v = e.target.value;
            setFilterGrade(v === "null" ? null : (v as Grade | "all"));
          }}
          className="pointer-events-auto px-3 py-2 text-sm bg-white border border-gray-300 rounded shadow-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
          aria-label="Filter by grade"
        >
          {gradeOptions.map((o) => (
            <option
              key={String(o.value)}
              value={o.value === null ? "null" : (o.value ?? "null")}
            >
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Loading overlay */}
      {loading && !geoError && (
        <div className="absolute inset-0 z-[999] flex items-center justify-center bg-gray-50">
          <p className="text-gray-500 text-sm">Loading map…</p>
        </div>
      )}

      {/* Error overlay */}
      {geoError && (
        <div className="absolute inset-0 z-[999] flex items-center justify-center bg-gray-50">
          <p className="text-red-600 text-sm max-w-xs text-center">{geoError}</p>
        </div>
      )}

      {/* Map container */}
      <div ref={mapRef} className="w-full h-full" />

      {/* Legend */}
      <div className="absolute bottom-6 right-3 z-[1000] bg-white border border-gray-200 rounded shadow-sm p-3 text-xs">
        <p className="font-semibold text-gray-700 mb-2 uppercase tracking-wide text-[10px]">
          Composite grade
        </p>
        {(
          [
            ["A", "Excellent"],
            ["B", "Good"],
            ["C", "Below avg"],
            ["D", "Poor"],
            ["F", "Failing"],
            [null, "No data"],
          ] as Array<[Grade, string]>
        ).map(([grade, label]) => (
          <div key={String(grade)} className="flex items-center gap-2 mb-1 last:mb-0">
            <span
              className="inline-block w-4 h-4 rounded-sm flex-shrink-0 border border-white"
              style={{ backgroundColor: GRADE_COLOR[grade ?? "null"] }}
            />
            <span className="text-gray-700">
              {grade} — {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
