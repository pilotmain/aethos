import type { Metadata } from "next";
import { MissionGraph } from "@/components/mission-control/MissionGraph";
import { MissionControlLiveEvents } from "@/components/mission-control/MissionControlLiveEvents";
import { MissionControlPage } from "@/components/mission-control/MissionControlPage";

export const metadata: Metadata = {
  title: "Mission Control · Nexa",
  description: "Priorities, approvals, and active work across Nexa.",
};

export default function MissionControlRoute() {
  return (
    <>
      <MissionControlLiveEvents />
      <MissionGraph />
      <MissionControlPage />
    </>
  );
}
