import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mission Control · AethOS",
  description: "Priorities, approvals, and active work across AethOS.",
};

export default function MissionControlRootLayout({ children }: { children: React.ReactNode }) {
  return children;
}
