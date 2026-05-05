"use client";

import Link from "next/link";

import { MobileNav } from "@/components/mission-control/MobileNav";
import { Button } from "@/components/ui/button";

export function Header() {
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-4 border-b border-zinc-800 bg-zinc-950/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-zinc-950/75">
      <MobileNav />

      <div className="flex min-w-0 flex-1 flex-col">
        <h1 className="truncate text-lg font-semibold tracking-tight text-zinc-100">Mission Control</h1>
        <p className="truncate text-xs text-zinc-500">Phase 33 — redesigned operator shell</p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/">Workspace</Link>
        </Button>
        <Button variant="outline" size="sm" asChild>
          <Link href="/login">Login</Link>
        </Button>
      </div>
    </header>
  );
}
