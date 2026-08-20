/** Sidebar structure, shared by the desktop sidebar and the mobile slide-over. */

export interface NavItem {
  href: string;
  label: string;
  icon: string;
}

export interface NavSection {
  title: string | null;
  items: NavItem[];
}

export const NAV: NavSection[] = [
  {
    title: null,
    items: [{ href: "/", label: "Dashboard", icon: "◫" }],
  },
  {
    title: "Predict",
    items: [
      { href: "/predict/single", label: "Single song", icon: "♪" },
      { href: "/predict/batch", label: "Batch CSV", icon: "≡" },
      { href: "/predict/spotify", label: "Spotify track", icon: "▶" },
      { href: "/predict/audio", label: "Local audio", icon: "◉" },
    ],
  },
  {
    title: "Analyse",
    items: [
      { href: "/insights", label: "Model evaluation", icon: "⌗" },
      { href: "/dataset", label: "Dataset explorer", icon: "⌸" },
      { href: "/history", label: "History", icon: "↻" },
    ],
  },
  {
    title: null,
    items: [{ href: "/settings", label: "Settings", icon: "⚙" }],
  },
];
