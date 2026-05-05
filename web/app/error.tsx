"use client";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center bg-zinc-950 p-6 text-center text-sm text-zinc-300">
      <p className="text-rose-300/90">Something went wrong in the AethOS web UI.</p>
      <p className="mt-1 max-w-md break-words text-zinc-500">{error.message}</p>
      <button
        type="button"
        onClick={() => reset()}
        className="mt-4 rounded-lg bg-white/10 px-4 py-2 text-zinc-100 hover:bg-white/15"
      >
        Try again
      </button>
    </div>
  );
}
