import type { Metadata } from "next";

import { MissionControlAuthGate } from "@/app/mission-control/MissionControlAuthGate";

export const metadata: Metadata = {
  title: "Mission Control · AethOS",
  description: "Priorities, approvals, and active work across AethOS.",
};

export default function MissionControlRootLayout({ children }: { children: React.ReactNode }) {
  return <MissionControlAuthGate>{children}</MissionControlAuthGate>;
}
