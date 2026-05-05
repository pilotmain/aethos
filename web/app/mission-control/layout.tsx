import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mission Control · Nexa",
  description: "Priorities, approvals, and active work across Nexa.",
};

export default function MissionControlRootLayout({ children }: { children: React.ReactNode }) {
  return children;
}
