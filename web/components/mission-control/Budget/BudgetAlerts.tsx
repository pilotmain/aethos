"use client";

import type { BudgetAlert } from "@/types/mission-control";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertCircle, AlertTriangle, Bell, BellOff, CheckCircle } from "lucide-react";

interface BudgetAlertsProps {
  alerts: BudgetAlert[];
  onAcknowledge: (alertId: string) => void;
}

const alertIcons = {
  warning: <AlertTriangle className="h-4 w-4 text-amber-400" />,
  critical: <AlertCircle className="h-4 w-4 text-red-400" />,
  exceeded: <Bell className="h-4 w-4 text-red-400" />,
};

export function BudgetAlerts({ alerts, onAcknowledge }: BudgetAlertsProps) {
  const unacknowledged = alerts.filter((a) => !a.acknowledged);

  if (unacknowledged.length === 0) {
    return (
      <div className="flex items-center justify-center gap-2 py-4 text-sm text-zinc-500">
        <BellOff className="h-4 w-4 shrink-0" />
        No active alerts
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {unacknowledged.map((alert) => (
        <Alert
          key={alert.id}
          variant={alert.type === "critical" || alert.type === "exceeded" ? "destructive" : "warning"}
        >
          <div className="flex gap-2">
            {alertIcons[alert.type]}
            <div className="min-w-0 flex-1 space-y-1">
              <AlertTitle>
                {alert.type === "warning" ? "Warning" : alert.type === "critical" ? "Critical" : "Budget exceeded"}
              </AlertTitle>
              <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-zinc-300">{alert.message}</span>
                <Button variant="outline" size="sm" className="shrink-0 border-zinc-600" onClick={() => onAcknowledge(alert.id)}>
                  <CheckCircle className="mr-1 h-3 w-3" />
                  Acknowledge
                </Button>
              </AlertDescription>
            </div>
          </div>
        </Alert>
      ))}
    </div>
  );
}
