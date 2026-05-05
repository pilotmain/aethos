"use client";

import { Menu } from "lucide-react";

import { Sidebar } from "@/components/mission-control/Sidebar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

export function MobileNav() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="icon" className="lg:hidden" aria-label="Open navigation menu">
          <Menu className="h-4 w-4" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 border-zinc-800 p-0">
        <Sidebar variant="drawer" />
      </SheetContent>
    </Sheet>
  );
}
