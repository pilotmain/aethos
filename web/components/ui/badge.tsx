import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 focus:ring-offset-zinc-950",
  {
    variants: {
      variant: {
        default: "border-transparent bg-violet-600 text-white",
        secondary: "border-zinc-700 bg-zinc-800 text-zinc-200",
        outline: "border-zinc-700 text-zinc-200",
        success: "border-transparent bg-emerald-600 text-white",
        warning: "border-transparent bg-amber-600 text-white",
        muted: "border-transparent bg-zinc-600 text-white",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
