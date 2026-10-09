// CARTO basemap tiles require an API key; without one every tile is watermarked.
// NEXT_PUBLIC_ vars are inlined at build time, so the key must be set before `next build`.
const CARTO_API_KEY = process.env.NEXT_PUBLIC_CARTO_API_KEY;

export const CARTO_ATTRIBUTION = "&copy; OpenStreetMap contributors &copy; CARTO";

export type CartoStyle = "light_nolabels" | "dark_nolabels";

export function cartoTileUrl(style: CartoStyle): string {
  const base = `https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}.png`;
  return CARTO_API_KEY ? `${base}?key=${encodeURIComponent(CARTO_API_KEY)}` : base;
}
