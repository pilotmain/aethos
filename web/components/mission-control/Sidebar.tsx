"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { missionControlPrimaryNav, missionControlSecondaryNav } from "@/lib/navigation";
import { cn } from "@/lib/utils";

import { MissionControlApiStatus } from "@/components/mission-control/MissionControlApiStatus";

import pkg from "../../package.json";

export type SidebarProps = {
  variant?: "desktop" | "drawer";
};

function NavSection({
  items,
  pathname,
}: {
  items: typeof missionControlPrimaryNav;
  pathname: string | null;
}) {
  return (
    <>
      {items.map((item) => {
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
              item.deprecated && "opacity-60",
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
    </>
  );
}

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
          <Link href="/mission-control/office" className="flex items-center gap-2 font-semibold text-zinc-100">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600 text-xs font-bold text-white">
              A
            </span>
            <span className="text-sm">Mission Control</span>
          </Link>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto p-2">
          <NavSection items={missionControlPrimaryNav} pathname={pathname} />
          <div>
            <p className="px-3 pb-1 text-[10px] font-medium uppercase tracking-wider text-zinc-500">More</p>
            <NavSection items={missionControlSecondaryNav} pathname={pathname} />
          </div>
        </nav>

        <div className="shrink-0 border-t border-zinc-800 p-4">
          <MissionControlApiStatus />
          <p className="mt-2 text-xs text-zinc-600">aethos-web v{pkg.version}</p>
        </div>
      </div>
    </aside>
  );
}
