"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { missionControlNavItems } from "@/lib/navigation";
import { cn } from "@/lib/utils";

import { MissionControlApiStatus } from "@/components/mission-control/MissionControlApiStatus";

import pkg from "../../package.json";

export type SidebarProps = {
  /** When true, sidebar is embedded in the mobile drawer (not fixed / not lg-only). */
  variant?: "desktop" | "drawer";
};

export function Sidebar({ variant = "desktop" }: SidebarProps) {
  const pathname = usePathname();

  const outerClass =
    variant === "desktop"
      ? "fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-zinc-800 bg-zinc-950 lg:block"
      : "flex h-full w-full flex-col border-0 bg-zinc-950";

  return (
    <aside className={outerClass}>
      <div className="flex h-full flex-col">
        <div className="flex h-14 shrink-0 items-center border-b border-zinc-800 px-4">
          <Link href="/mission-control/overview" className="flex items-center gap-2 font-semibold text-zinc-100">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600 text-xs font-bold text-white">
              N
            </span>
            <span>AethOS Mission</span>
          </Link>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {missionControlNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = (() => {
              if (!pathname) return false;
              if (pathname === item.href) return true;
              if (item.href === "/mission-control/overview") return false;
              return pathname.startsWith(`${item.href}/`);
            })();

            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.description}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-violet-600 text-white shadow-sm"
                    : "text-zinc-300 hover:bg-zinc-800/90 hover:text-white",
                )}
              >
                <Icon className="h-4 w-4 shrink-0 opacity-90" aria-hidden />
                {item.name}
              </Link>
            );
          })}
        </nav>

        <div className="shrink-0 border-t border-zinc-800 p-4">
          <MissionControlApiStatus />
          <p className="mt-2 text-xs text-zinc-600">aethos-web v{pkg.version}</p>
        </div>
      </div>
    </aside>
  );
}
