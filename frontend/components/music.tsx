"use client";

/**
 * Small musical motifs used as UI chrome: an equaliser, a vinyl mark and a
 * waveform rule. They are decorative, so each is hidden from assistive tech and
 * every one of them freezes under `prefers-reduced-motion` (handled in CSS).
 */

/** Animated level meter. `playing` false leaves the bars frozen low. */
export function EqualizerBars({
  playing = true,
  className = "",
  barClassName = "bg-brand",
}: {
  playing?: boolean;
  className?: string;
  barClassName?: string;
}) {
  const heights = ["h-2", "h-3.5", "h-2.5", "h-3"];
  return (
    <span
      aria-hidden
      className={`inline-flex h-4 items-end gap-[2px] ${className}`}
    >
      {heights.map((height, index) => (
        <span
          key={index}
          className={`w-[3px] rounded-full ${height} ${barClassName} ${
            playing ? "eq-bar" : "eq-bar-idle"
          }`}
        />
      ))}
    </span>
  );
}

/** Vinyl record brand mark; the disc spins only while `spinning`. */
export function VinylMark({
  size = 26,
  spinning = false,
}: {
  size?: number;
  spinning?: boolean;
}) {
  return (
    <span
      aria-hidden
      className={`inline-block shrink-0 ${spinning ? "animate-disc" : ""}`}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 32 32" width={size} height={size}>
        <circle cx="16" cy="16" r="15" fill="#14161a" />
        <circle cx="16" cy="16" r="11.5" fill="none" stroke="#3a3f48" strokeWidth="0.7" />
        <circle cx="16" cy="16" r="9" fill="none" stroke="#3a3f48" strokeWidth="0.7" />
        <circle cx="16" cy="16" r="6.5" fill="none" stroke="#3a3f48" strokeWidth="0.7" />
        <circle cx="16" cy="16" r="4.6" fill="var(--color-brand)" />
        <circle cx="16" cy="16" r="1.2" fill="#ffffff" />
      </svg>
    </span>
  );
}

/**
 * Waveform rule used instead of a plain divider. Bars are generated from a fixed
 * seed so the shape is identical between server and client render.
 */
export function WaveformDivider({ className = "" }: { className?: string }) {
  const COUNT = 96;
  const bars = Array.from({ length: COUNT }, (_, i) => {
    // Deterministic — no Math.random, so server and client render identically.
    const detail =
      Math.sin(i * 0.9) * 0.45 + Math.sin(i * 0.31) * 0.35 + Math.sin(i * 2.1) * 0.2;
    // Envelope tapers towards both ends so the run reads as a clip, not a fence.
    const envelope = Math.sin((i / (COUNT - 1)) * Math.PI) ** 0.65;
    return 2 + Math.round(Math.abs(detail) * envelope * 20);
  });

  return (
    <div
      aria-hidden
      className={`flex h-6 items-center justify-center gap-[2px] overflow-hidden ${className}`}
    >
      {bars.map((height, index) => (
        <span
          key={index}
          className="w-[3px] shrink-0 rounded-full bg-edge-strong"
          style={{ height: `${height}px` }}
        />
      ))}
    </div>
  );
}
