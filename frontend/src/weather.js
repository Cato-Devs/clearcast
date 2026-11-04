// Display text for the events and bands in docs/prediction-format.md, and helpers for them.

export const EVENTS = [
  { id: "rain", label: "Rain", detail: "At least 1 mm in the next 6 hours" },
  { id: "heavy_rain", label: "Heavy rain", detail: "At least 10 mm in the next 6 hours" },
  { id: "flood_risk", label: "Flood risk", detail: "Heavy rain on wet ground in the next 24 hours" },
  { id: "hot", label: "Hot", detail: "Reaches 35°C in the next 6 hours" },
  { id: "cold", label: "Cold", detail: "Falls to 12°C in the next 6 hours" },
  { id: "sunny", label: "Sunny", detail: "Average cloud cover of 30% or less in the next 6 hours" },
  { id: "strong_wind", label: "Strong wind", detail: "Gusts of about 43 km/h in the next 6 hours" },
];

export const BANDS = [
  { id: "very_unlikely", label: "Very unlikely" },
  { id: "unlikely", label: "Unlikely" },
  { id: "likely", label: "Likely" },
  { id: "very_likely", label: "Very likely" },
];

export const NO_DATA = { id: "no_data", label: "No recent data" };

// An old prediction must not look current: "very unlikely" from yesterday tells you nothing.
const MAX_AGE_HOURS = 3;

export function isCurrent(prediction, now = Date.now()) {
  return now - new Date(prediction.issued_at).getTime() <= MAX_AGE_HOURS * 3600 * 1000;
}

/** The band to display for one location and event: its real band, or no_data if missing or old. */
export function displayBand(run, eventId) {
  const prediction = run?.predictions.find((p) => p.event === eventId);
  if (!prediction || !isCurrent(prediction)) return NO_DATA;
  return BANDS.find((b) => b.id === prediction.band) ?? NO_DATA;
}

/** A time in East Africa Time, for example "Wed 4 Nov, 9:00 pm". */
export function formatEat(utcText) {
  return new Intl.DateTimeFormat("en-KE", {
    timeZone: "Africa/Nairobi",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true, // "4:00" alone could be morning or afternoon
  }).format(new Date(utcText));
}
