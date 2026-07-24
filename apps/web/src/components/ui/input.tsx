import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

export function Input({ className, type, ...props }: ComponentProps<"input">) {
  return (
    <input
      type={type}
      className={cn(
        "h-11 w-full rounded-xl border border-input bg-background px-3.5 text-sm shadow-xs outline-none transition-[border-color,box-shadow] placeholder:text-muted-foreground/75 focus:border-primary/50 focus:ring-3 focus:ring-primary/10 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  )
}
