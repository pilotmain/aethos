import Link from "next/link";

export default function MissionControlAdvancedPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-zinc-50">Advanced</h2>
        <p className="mt-2 max-w-prose text-sm text-zinc-400">
          Advanced settings, integrations, and dense operator tools will consolidate here.
        </p>
      </div>
      <p className="text-sm text-zinc-500">
        The existing multi-panel Mission Control console remains available at{" "}
        <Link href="/mission-control/legacy" className="text-violet-400 underline-offset-2 hover:underline">
          /mission-control/legacy
        </Link>{" "}
        until those flows are migrated.
      </p>
    </div>
  );
}
