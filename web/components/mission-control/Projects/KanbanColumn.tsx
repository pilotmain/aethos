"use client";

import { useDroppable } from "@dnd-kit/core";

import type { Task } from "@/types/mission-control";
import { KanbanCard } from "@/components/mission-control/Projects/KanbanCard";

import { cn } from "@/lib/utils";

interface KanbanColumnProps {
  id: string;
  title: string;
  tasks: Task[];
  onTaskClick: (task: Task) => void;
  color?: string;
  readOnly?: boolean;
}

export function KanbanColumn({ id, title, tasks, onTaskClick, color, readOnly }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div className="flex h-full min-h-[500px] flex-col rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-medium text-zinc-100">
          {title}
          <span className="ml-2 text-xs font-normal text-zinc-500">({tasks.length})</span>
        </h3>
        {color ? <div className={cn("h-2 w-2 shrink-0 rounded-full", color)} /> : null}
      </div>

      <div ref={setNodeRef} className={cn("flex-1 space-y-2 rounded-md transition-colors", isOver && "bg-violet-500/5")}>
        {tasks.map((task) => (
          <KanbanCard
            key={task.id}
            task={task}
            dragId={`kanban-${task.id}`}
            draggable={!readOnly}
            onClick={onTaskClick}
          />
        ))}
        {tasks.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-500">No tasks</div>
        ) : null}
      </div>
    </div>
  );
}
