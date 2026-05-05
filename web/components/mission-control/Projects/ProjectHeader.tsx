"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import type { Project } from "@/types/mission-control";
import { Button } from "@/components/ui/button";
import { ChevronLeft } from "lucide-react";

interface ProjectHeaderProps {
  project: Project | null;
  actions?: ReactNode;
}

export function ProjectHeader({ project, actions }: ProjectHeaderProps) {
  return (
    <div className="flex flex-col gap-4 border-b border-zinc-800 pb-6 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0 space-y-2">
        <Button variant="ghost" size="sm" className="-ml-2 w-fit gap-1 text-zinc-400 hover:text-zinc-100" asChild>
          <Link href="/mission-control/projects">
            <ChevronLeft className="h-4 w-4" />
            All projects
          </Link>
        </Button>
        {project ? (
          <>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-50">{project.name}</h1>
            <p className="text-sm text-zinc-400">{project.goal}</p>
            {project.kind_label ? (
              <p className="text-xs uppercase tracking-wide text-zinc-500">{project.kind_label}</p>
            ) : null}
          </>
        ) : (
          <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Project</h1>
        )}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
