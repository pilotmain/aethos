import Link from "next/link";

export default function MissionControlOverviewPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-zinc-50">Overview</h2>
        <p className="mt-2 max-w-prose text-sm text-zinc-400">
          Phase 33 M1 shell — dashboard cards and metrics will land in the next milestones.
        </p>
      </div>
      <p className="text-sm text-zinc-500">
        Need the full classic console? Open{" "}
        <Link href="/mission-control/legacy" className="text-violet-400 underline-offset-2 hover:underline">
          Classic Mission Control
        </Link>
        .
      </p>
    </div>
  );
}
