import type { Metadata } from "next";
import { MissionControlLayout } from "@/components/mission-control/MissionControlLayout";

export const metadata: Metadata = {
  title: "Mission Control · Nexa",
  description: "Priorities, approvals, and active work across Nexa.",
};

export default function MissionControlRoute() {
  return <MissionControlLayout />;
}
