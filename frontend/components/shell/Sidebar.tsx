"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { VinylMark } from "@/components/music";

import { NAV } from "./nav";
import { RetrainButton } from "./RetrainButton";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="flex h-full flex-col gap-6 overflow-y-auto p-4" aria-label="Main">
      <Link
        href="/"
        onClick={onNavigate}
        className="flex items-center gap-2 px-2 py-1 text-lg font-bold tracking-tight"
      >
        <VinylMark size={24} />
        HitLab
      </Link>

      {NAV.map((section, index) => (
        <div key={section.title ?? `section-${index}`} className="space-y-1">
          {section.title ? (
            <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
              {section.title}
            </div>
          ) : null}
          {section.items.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-brand-tint font-semibold text-brand-strong"
                    : "text-muted hover:bg-elevated hover:text-ink"
                }`}
              >
                <span aria-hidden className="w-4 text-center opacity-80">
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}

      {/* Action rather than navigation, so it sits apart from the linked sections. */}
      <div className="mt-auto">
        <RetrainButton />
      </div>
    </nav>
  );
}
