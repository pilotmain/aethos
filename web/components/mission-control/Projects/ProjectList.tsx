"use client";

import Link from "next/link";

import type { Project } from "@/types/mission-control";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface ProjectListProps {
  projects: Project[];
}

const statusConfig: Record<
  Project["status"],
  { label: string; className: string }
> = {
  active: { label: "Active", className: "border-transparent bg-emerald-600 text-white" },
  paused: { label: "Paused", className: "border-transparent bg-amber-600 text-white" },
  completed: { label: "Completed", className: "border-transparent bg-sky-600 text-white" },
  archived: { label: "Archived", className: "border-transparent bg-zinc-600 text-white" },
};

export function ProjectList({ projects }: ProjectListProps) {
  if (projects.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-center">
        <p className="text-zinc-400">No projects yet</p>
        <p className="text-sm text-zinc-500">Create a workspace folder mapping or open your checklist board.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <Link key={project.id} href={`/mission-control/projects/${project.id}`}>
          <Card className="h-full cursor-pointer transition-colors hover:border-violet-500/60">
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="line-clamp-1 text-base">{project.name}</CardTitle>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  {project.kind_label ? (
                    <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
                      {project.kind_label}
                    </Badge>
                  ) : null}
                  <Badge className={statusConfig[project.status].className}>{statusConfig[project.status].label}</Badge>
                </div>
              </div>
              <CardDescription className="line-clamp-2">{project.goal}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-zinc-400">
                  <span>Progress</span>
                  <span>{project.progress}%</span>
                </div>
                <Progress value={project.progress} max={100} className="h-2" />
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
