"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { TownRecord, Grade } from "@/src/types/town";

export type ActiveDimension = "composite" | "zoning" | "legislators" | "production" | "affordability" | "mbta";

export const DIMENSION_LABELS: Record<ActiveDimension, string> = {
  composite:    "Composite grade",
  zoning:       "Zoning permissiveness",
  legislators:  "Legislator record",
  production:   "Housing production",
  affordability:"Affordability",
  mbta:         "MBTA compliance",
};

function getGrade(town: TownRecord | undefined, dim: ActiveDimension): Grade {
  if (!town?.grades) return null;
  return town.grades[dim] ?? null;
}

// Grade color palette (matches gradeConfig in GradeBadge)
const GRADE_COLOR: Record<NonNullable<Grade> | "null", string> = {
  A: "#2d6a4f",
  B: "#52b788",
  C: "#e9c46a",
  D: "#e07b39",
  F: "#c1121f",
  null: "#d0cdc8",
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
  dimension: ActiveDimension;
}

export default function Map({ towns, dimension }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMapRef = useRef<import("leaflet").Map | null>(null);
  const layerRef = useRef<import("leaflet").GeoJSON | null>(null);
  const router = useRouter();

  const [search, setSearch] = useState("");
  const [geoError, setGeoError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const townIndex = useRef(buildTownIndex(towns));
  const dimensionRef = useRef<ActiveDimension>(dimension);

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

      // Light CartoDB base (geography, no labels) — clean gray geographic context
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
        {
          attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
          subdomains: "abcd",
          maxZoom: 19,
        }
      ).addTo(map);

      // Tooltip — styles applied via .ma-tooltip in globals.css
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
          fillOpacity: 0.78,
          color: "#666660",
          weight: 0.8,
          opacity: 0.6,
        };
      }

      function getTownByProps(
        props: Record<string, unknown>
      ): TownRecord | undefined {
        const geoid = getGeoid(props);
        return geoid ? townIndex.current[geoid] : undefined;
      }

      const isTouchDevice = () =>
        typeof window !== "undefined" &&
        window.matchMedia("(pointer: coarse)").matches;

      // Types for mobile two-tap state stored on Leaflet objects
      type MobileLayer = import("leaflet").Path & { _mobileSelected?: boolean };
      type MobileMap = import("leaflet").Map & {
        _mobileSelectedLayer?: MobileLayer;
      };

      const geoLayer = L.geoJSON(geojsonData, {
        style: (feature) => {
          const props = (feature?.properties ?? {}) as Record<string, unknown>;
          const grade = getGrade(getTownByProps(props), dimensionRef.current);
          return styleFeature(feature, grade);
        },
        onEachFeature(feature, layer) {
          const props = (feature.properties ?? {}) as Record<string, unknown>;
          const town = getTownByProps(props);
          const townName =
            town?.name ??
            (props["census_name"] as string | undefined) ??
            "Unknown";
          const fips = town?.fips ?? null;

          if (!isTouchDevice()) {
            // Desktop: original hover + direct-click behavior unchanged
            layer.on({
              mouseover(e) {
                const grade = getGrade(town, dimensionRef.current);
                const gradeColor = GRADE_COLOR[grade ?? "null"];
                const target = e.target as import("leaflet").Path;
                target.setStyle({
                  fillOpacity: 0.92,
                  weight: 1.5,
                  color: "#333330",
                  opacity: 1,
                });
                tooltip
                  .setLatLng(e.latlng)
                  .setContent(
                    `<span style="font-weight:600;color:#1a1816">${townName}</span>` +
                    `<br/><span style="color:#5a5450;font-size:12px">Grade </span>` +
                    `<span style="font-family:'DM Mono',monospace;font-weight:500;color:${gradeColor}">${grade ?? "–"}</span>`
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
          } else {
            // Mobile: first tap highlights + shows popup, second tap navigates
            layer.on({
              click(e) {
                if (!fips) return;
                const mobileLayer = layer as MobileLayer;
                const mobileMap = map as MobileMap;

                // Second tap on the already-selected town → navigate
                if (mobileLayer._mobileSelected) {
                  router.push(`/town/${fips}`);
                  return;
                }

                // Deselect any previously selected layer
                if (mobileMap._mobileSelectedLayer) {
                  mobileMap._mobileSelectedLayer._mobileSelected = false;
                  geoLayer.resetStyle(mobileMap._mobileSelectedLayer);
                  (mobileMap._mobileSelectedLayer as import("leaflet").Layer).closePopup();
                }

                // Select this layer
                mobileLayer._mobileSelected = true;
                mobileMap._mobileSelectedLayer = mobileLayer;

                // Highlight the tapped polygon
                (layer as import("leaflet").Path).setStyle({
                  fillOpacity: 0.92,
                  weight: 1.5,
                  color: "#333330",
                  opacity: 1,
                });

                // Show popup with town name, grade, and navigate link
                const grade = getGrade(town, dimensionRef.current);
                layer.bindPopup(
                  `<div style="font-family: inherit; min-width: 140px;">
                    <div style="font-size: 13px; font-weight: 600; margin-bottom: 6px;">${townName}</div>
                    <div style="font-size: 12px; color: #5a5450; margin-bottom: 10px;">
                      ${DIMENSION_LABELS[dimensionRef.current]}: <strong>${grade ?? "N/A"}</strong>
                    </div>
                    <a href="/town/${fips}"
                       style="display: block; text-align: center; background: #1a1816;
                              color: #f0ede8; padding: 6px 12px; border-radius: 4px;
                              text-decoration: none; font-size: 12px; font-weight: 500;">
                      View profile →
                    </a>
                  </div>`,
                  { closeButton: true, autoClose: true, closeOnClick: false }
                ).openPopup();

                // Stop propagation so the map-level click handler doesn't
                // immediately dismiss the popup we just opened
                e.originalEvent.stopPropagation();
              },
            });
          }
        },
      });

      geoLayer.addTo(map);
      layerRef.current = geoLayer;

      // Mobile: tapping the map background dismisses the active popup/highlight
      map.on("click", () => {
        const mobileMap = map as MobileMap;
        if (mobileMap._mobileSelectedLayer) {
          mobileMap._mobileSelectedLayer._mobileSelected = false;
          geoLayer.resetStyle(mobileMap._mobileSelectedLayer);
          mobileMap._mobileSelectedLayer = undefined;
        }
      });

      // Fit map to MA bounds — maxZoom: 8 ensures surrounding states remain visible
      try {
        const bounds = geoLayer.getBounds();
        if (bounds.isValid())
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
      } catch {
        // keep default center/zoom
      }

      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Restyle all layers when the active dimension changes
  useEffect(() => {
    dimensionRef.current = dimension;
    const layer = layerRef.current;
    if (!layer) return;
    layer.eachLayer((l) => {
      const gl = l as import("leaflet").Path & { feature?: GeoJSON.Feature };
      const props = (gl.feature?.properties ?? {}) as Record<string, unknown>;
      const geoid = getGeoid(props);
      const town = geoid ? townIndex.current[geoid] : undefined;
      const grade = getGrade(town, dimension);
      gl.setStyle({
        fillColor: GRADE_COLOR[grade ?? "null"],
        fillOpacity: 0.78,
      });
    });
  }, [dimension]);

  // Search: fly to matched town
  function handleSearch(query: string) {
    setSearch(query);
    if (!query.trim() || !leafletMapRef.current || !layerRef.current) return;

    const q = query.toLowerCase().trim();
    // Use an array so TypeScript doesn't narrow the closure assignment to never
    const matchedLayers: (import("leaflet").Layer & {
      feature?: GeoJSON.Feature;
    })[] = [];

    layerRef.current.eachLayer((l) => {
      if (matchedLayers.length > 0) return;
      const gl = l as import("leaflet").Layer & { feature?: GeoJSON.Feature };
      const props = (gl.feature?.properties ?? {}) as Record<string, unknown>;
      const geoid = getGeoid(props);
      const town = geoid ? townIndex.current[geoid] : undefined;
      const displayName =
        town?.name ??
        (props["census_name"] as string | undefined) ??
        "";
      if (displayName.toLowerCase().includes(q)) {
        matchedLayers.push(gl);
      }
    });

    const matchedLayer = matchedLayers[0];
    if (matchedLayer && leafletMapRef.current) {
      try {
        const asGeo = matchedLayer as unknown as {
          getBounds: () => import("leaflet").LatLngBounds;
        };
        const bounds = asGeo.getBounds();
        if (bounds?.isValid()) {
          leafletMapRef.current.flyToBounds(bounds, {
            padding: [40, 40],
            duration: 0.8,
          });
        }
      } catch {
        // Polygon may not have getBounds
      }
      (matchedLayer as unknown as import("leaflet").Path).setStyle({
        color: "#1a1816",
        weight: 2.5,
      });
      setTimeout(() => {
        layerRef.current?.resetStyle(
          matchedLayer as unknown as import("leaflet").Path
        );
      }, 2500);
    }
  }

  const controlStyle: React.CSSProperties = {
    backgroundColor: "#ffffff",
    border: "1px solid #e0ddd8",
    color: "#1a1816",
    fontSize: "14px",
    borderRadius: "6px",
    boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
    outline: "none",
  };

  return (
    <div className="relative w-full h-full">
      {/* Controls — positioned to the right of Leaflet zoom buttons (left: 60px) */}
      <div
        className="absolute flex flex-wrap gap-2 pointer-events-none"
        style={{ top: "12px", left: "60px", zIndex: 1001 }}
      >
        <input
          type="search"
          placeholder="Search municipality…"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="pointer-events-auto px-3 py-2 w-52"
          style={controlStyle}
          aria-label="Search municipality"
        />
      </div>

      {/* Loading overlay */}
      {loading && !geoError && (
        <div
          className="absolute inset-0 z-[999] flex items-center justify-center"
          style={{ backgroundColor: "var(--bg-primary)" }}
        >
          <p
            className="text-sm font-mono"
            style={{ color: "var(--text-muted)" }}
          >
            Loading map…
          </p>
        </div>
      )}

      {/* Error overlay */}
      {geoError && (
        <div
          className="absolute inset-0 z-[999] flex items-center justify-center"
          style={{ backgroundColor: "var(--bg-primary)" }}
        >
          <p
            className="text-sm max-w-xs text-center"
            style={{ color: "#e63946" }}
          >
            {geoError}
          </p>
        </div>
      )}

      {/* Map container */}
      <div ref={mapRef} className="w-full h-full" />

      {/* Legend */}
      <div
        className="absolute bottom-6 right-3 z-[1000] rounded p-3 text-xs"
        style={{
          backgroundColor: "#ffffff",
          border: "1px solid #e0ddd8",
          boxShadow: "0 1px 6px rgba(0,0,0,0.10)",
        }}
      >
        <p
          className="mb-2 uppercase tracking-wide font-mono"
          style={{ fontSize: "10px", color: "#9a9088" }}
        >
          {DIMENSION_LABELS[dimension]}
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
          <div
            key={String(grade)}
            className="flex items-center gap-2 mb-1 last:mb-0"
          >
            <span
              className="inline-block w-3.5 h-3.5 rounded-sm flex-shrink-0"
              style={{
                backgroundColor: GRADE_COLOR[grade ?? "null"],
                border: "1px solid rgba(0,0,0,0.15)",
              }}
            />
            <span style={{ color: "#5a5450" }}>
              {grade ?? "–"} — {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
