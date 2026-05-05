"use client";

import { useMemo, useState } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  MouseSensor,
  TouchSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";

import type { KanbanColumnType, Task } from "@/types/mission-control";
import { KanbanColumn } from "@/components/mission-control/Projects/KanbanColumn";
import { KanbanCardOverlay } from "@/components/mission-control/Projects/KanbanCard";
import { TaskDetailDialog } from "@/components/mission-control/Projects/TaskDetailDialog";

interface KanbanBoardProps {
  tasks: Task[];
  readOnly?: boolean;
  onTaskStatusChange?: (taskId: string, newStatus: KanbanColumnType) => Promise<void>;
  onTasksRefresh?: () => void | Promise<void>;
}

const columns: { id: KanbanColumnType; title: string; color: string }[] = [
  { id: "pending", title: "To Do", color: "bg-amber-500" },
  { id: "in_progress", title: "In Progress", color: "bg-sky-500" },
  { id: "done", title: "Done", color: "bg-emerald-500" },
];

function columnForTaskStatus(st: Task["status"]): KanbanColumnType {
  if (st === "done") return "done";
  if (st === "in_progress") return "in_progress";
  return "pending";
}

function resolveDropColumn(overId: string | undefined | null, tasks: Task[]): KanbanColumnType | null {
  if (!overId) return null;
  const direct = columns.find((c) => c.id === overId);
  if (direct) return direct.id;
  const prefix = "kanban-";
  if (overId.startsWith(prefix)) {
    const id = overId.slice(prefix.length);
    const hit = tasks.find((t) => t.id === id);
    if (hit) return columnForTaskStatus(hit.status);
  }
  return null;
}

export function KanbanBoard({ tasks, readOnly, onTaskStatusChange, onTasksRefresh }: KanbanBoardProps) {
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 6 } }),
  );

  const tasksByStatus = useMemo(() => {
    const grouped: Record<KanbanColumnType, Task[]> = { pending: [], in_progress: [], done: [] };
    for (const t of tasks) {
      grouped[columnForTaskStatus(t.status)].push(t);
    }
    return grouped;
  }, [tasks]);

  const handleDragStart = (event: DragStartEvent) => {
    const raw = String(event.active.id);
    if (!raw.startsWith("kanban-")) return;
    const id = raw.slice("kanban-".length);
    const task = tasks.find((t) => t.id === id);
    if (task) setActiveTask(task);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveTask(null);
    if (readOnly || !onTaskStatusChange) return;

    const nextCol = resolveDropColumn(over?.id ? String(over.id) : null, tasks);
    if (!nextCol) return;

    const raw = String(active.id);
    if (!raw.startsWith("kanban-")) return;
    const taskId = raw.slice("kanban-".length);
    const task = tasks.find((t) => t.id === taskId);
    if (!task || columnForTaskStatus(task.status) === nextCol) return;

    await onTaskStatusChange(taskId, nextCol);
  };

  const handleTaskClick = (task: Task) => {
    setSelectedTask(task);
    setDialogOpen(true);
  };

  const handleAfterTaskSaved = async () => {
    await onTasksRefresh?.();
    setDialogOpen(false);
  };

  return (
    <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {columns.map((column) => (
          <KanbanColumn
            key={column.id}
            id={column.id}
            title={column.title}
            tasks={tasksByStatus[column.id]}
            onTaskClick={handleTaskClick}
            color={column.color}
            readOnly={readOnly}
          />
        ))}
      </div>

      <DragOverlay dropAnimation={null}>{activeTask ? <KanbanCardOverlay task={activeTask} /> : null}</DragOverlay>

      <TaskDetailDialog
        open={dialogOpen}
        task={selectedTask}
        readOnly={readOnly}
        onClose={() => setDialogOpen(false)}
        onAfterSave={handleAfterTaskSaved}
      />
    </DndContext>
  );
}
