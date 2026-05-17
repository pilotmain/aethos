import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Briefcase,
  ClipboardList,
  Cloud,
  FileText,
  CreditCard,
  FolderKanban,
  LayoutDashboard,
  Package,
  Plug,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  Star,
  Users,
} from "lucide-react";

export type MissionControlNavItem = {
  name: string;
  href: string;
  icon: LucideIcon;
  description: string;
  deprecated?: boolean;
};

/** Primary Mission Control navigation (Phase 3 Step 4). */
export const missionControlPrimaryNav: MissionControlNavItem[] = [
  {
    name: "Office",
    href: "/mission-control/office",
    icon: Users,
    description: "AethOS Orchestrator and runtime workers",
  },
  {
    name: "Runtime",
    href: "/mission-control/runtime-overview",
    icon: Activity,
    description: "Runtime health, readiness, and trust",
  },
  {
    name: "Deployments",
    href: "/mission-control/projects",
    icon: FolderKanban,
    description: "Projects, deployments, and repairs",
  },
  {
    name: "Providers",
    href: "/mission-control/providers",
    icon: Cloud,
    description: "Provider inventory and recent actions",
  },
  {
    name: "Marketplace",
    href: "/mission-control/marketplace",
    icon: Package,
    description: "Skill marketplace — AI execution extensions",
  },
  {
    name: "Privacy",
    href: "/mission-control/privacy",
    icon: Shield,
    description: "Privacy posture and egress decisions",
  },
  {
    name: "Governance",
    href: "/mission-control/governance",
    icon: ClipboardList,
    description: "Operational timeline — who did what",
  },
  {
    name: "Settings",
    href: "/mission-control/advanced",
    icon: Settings,
    description: "Integrations and configuration",
  },
];

/** Secondary / legacy routes — nested under More in the sidebar. */
export const missionControlSecondaryNav: MissionControlNavItem[] = [
  {
    name: "Deliverables",
    href: "/mission-control/deliverables",
    icon: FileText,
    description: "Worker outputs — search, filter, export",
  },
  {
    name: "Workspace",
    href: "/mission-control/workspace-intelligence",
    icon: FolderKanban,
    description: "Workspace intelligence, risk, research continuity",
  },
  {
    name: "Runtime supervision",
    href: "/mission-control/runtime-supervision",
    icon: ShieldCheck,
    description: "Process ownership, SQLite, Telegram, hydration locks",
  },
  {
    name: "Runtime recovery",
    href: "/mission-control/runtime-recovery",
    icon: Activity,
    description: "Hydration recovery and degraded mode guidance",
  },
  {
    name: "Insights",
    href: "/mission-control/operational-insights",
    icon: Activity,
    description: "Legacy — prefer Runtime overview and intelligence routes",
    deprecated: true,
  },
  {
    name: "Welcome",
    href: "/mission-control/onboarding",
    icon: Sparkles,
    description: "First-run Mission Control walkthrough",
  },
  {
    name: "Executive overview",
    href: "/mission-control/executive-overview",
    icon: Briefcase,
    description: "Enterprise operational posture — executive-readable",
  },
  {
    name: "Runtime story",
    href: "/mission-control/runtime-story",
    icon: Sparkles,
    description: "Operational narratives and continuity storyline",
  },
  {
    name: "Explainability",
    href: "/mission-control/explainability",
    icon: ShieldCheck,
    description: "Runtime decision explanations",
  },
  {
    name: "Runtime plugins",
    href: "/mission-control/plugins",
    icon: Plug,
    description: "Operational runtime extensions (not skills)",
  },
  {
    name: "Advantages",
    href: "/mission-control/differentiators",
    icon: Star,
    description: "Why AethOS vs OpenClaw",
  },
  {
    name: "CEO (legacy)",
    href: "/mission-control/ceo",
    icon: Briefcase,
    description: "Deprecated — use Office for runtime agents",
    deprecated: true,
  },
  {
    name: "Team",
    href: "/mission-control/team",
    icon: Users,
    description: "Team members and roles",
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
    description: "High-risk actions awaiting sign-off",
  },
  {
    name: "Audit logs",
    href: "/mission-control/admin/audit",
    icon: ClipboardList,
    description: "Enterprise audit trail",
  },
  {
    name: "Improvements",
    href: "/mission-control/self-improvement",
    icon: Sparkles,
    description: "Self-improvement proposals",
  },
];

/** @deprecated Use missionControlPrimaryNav + missionControlSecondaryNav */
export const missionControlNavItems: MissionControlNavItem[] = [
  ...missionControlPrimaryNav,
  ...missionControlSecondaryNav,
];
