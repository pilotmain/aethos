import type { LucideIcon } from "lucide-react";
import {
  Briefcase,
  CreditCard,
  FolderKanban,
  LayoutDashboard,
  Package,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";

export type MissionControlNavItem = {
  name: string;
  href: string;
  icon: LucideIcon;
  description: string;
};

export const missionControlNavItems: MissionControlNavItem[] = [
  {
    name: "Overview",
    href: "/mission-control/overview",
    icon: LayoutDashboard,
    description: "Dashboard and key metrics",
  },
  {
    name: "CEO",
    href: "/mission-control/ceo",
    icon: Briefcase,
    description: "Agent oversight and performance",
  },
  {
    name: "Team",
    href: "/mission-control/team",
    icon: Users,
    description: "Team members and roles",
  },
  {
    name: "Projects",
    href: "/mission-control/projects",
    icon: FolderKanban,
    description: "Projects and tasks",
  },
  {
    name: "Budget",
    href: "/mission-control/budget",
    icon: CreditCard,
    description: "Usage and costs",
  },
  {
    name: "Approvals",
    href: "/mission-control/approvals",
    icon: ShieldCheck,
    description: "High-risk actions awaiting human sign-off",
  },
  {
    name: "Marketplace",
    href: "/mission-control/marketplace",
    icon: Package,
    description: "Discover and install ClawHub community skills",
  },
  {
    name: "Improvements",
    href: "/mission-control/self-improvement",
    icon: Sparkles,
    description: "Self-improvement proposals (owner-gated, sandboxed)",
  },
  {
    name: "Advanced",
    href: "/mission-control/advanced",
    icon: Settings,
    description: "Settings and integrations",
  },
];
