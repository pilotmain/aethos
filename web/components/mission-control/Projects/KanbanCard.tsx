"use client";

import type { ReactNode } from "react";
import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";

import type { Task } from "@/types/mission-control";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, CheckCircle, Clock, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface KanbanCardProps {
  task: Task;
  dragId: string;
  draggable?: boolean;
  onClick: (task: Task) => void;
}

const statusIcon: Record<Task["status"], ReactNode> = {
  pending: <Clock className="h-3 w-3 text-amber-400" />,
  in_progress: <Loader2 className="h-3 w-3 animate-spin text-sky-400" />,
  done: <CheckCircle className="h-3 w-3 text-emerald-400" />,
  blocked: <AlertCircle className="h-3 w-3 text-red-400" />,
};

function KanbanCardFace({
  task,
  className,
  onClick,
}: {
  task: Task;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <Card
      className={cn(
        "transition-all hover:border-zinc-600 hover:shadow-md",
        onClick && "cursor-pointer",
        className,
      )}
      onClick={onClick}
    >
      <CardHeader className="p-3 pb-0">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="line-clamp-2 text-sm font-medium leading-snug">{task.title}</CardTitle>
          {statusIcon[task.status]}
        </div>
      </CardHeader>
      <CardContent className="p-3 pt-2">
        {task.description ? (
          <p className="line-clamp-2 text-xs text-zinc-500">{task.description}</p>
        ) : null}
        {task.assigned_to_name ? (
          <p className="mt-2 text-xs text-zinc-500">{task.assigned_to_name}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** Drag overlay preview — avoids mounting a second `useDraggable` instance. */
export function KanbanCardOverlay({ task }: { task: Task }) {
  return <KanbanCardFace task={task} className="rotate-2 shadow-xl ring-2 ring-violet-500/40" />;
}

export function KanbanCard({ task, dragId, draggable = true, onClick }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: dragId,
    disabled: !draggable,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn("touch-none", isDragging && "z-10 opacity-90")}
      {...(draggable ? listeners : {})}
      {...(draggable ? attributes : {})}
    >
      <KanbanCardFace
        task={task}
        className={cn(draggable ? "cursor-grab active:cursor-grabbing" : "cursor-default")}
        onClick={() => onClick(task)}
      />
    </div>
  );
}
