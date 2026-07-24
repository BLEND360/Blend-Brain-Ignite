import { BrainCircuit } from "lucide-react"
import { Link } from "react-router-dom"

import { cn } from "@/lib/utils"

type BrandProps = {
  compact?: boolean
  inverse?: boolean
}

export function Brand({ compact = false, inverse = false }: BrandProps) {
  return (
    <Link
      to="/"
      aria-label="Blend Knowledge Brain home"
      className={cn(
        "inline-flex items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
        inverse ? "text-white" : "text-foreground",
      )}
    >
      <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-[#5b7cff] to-[#19a7a0] text-white shadow-lg shadow-blue-950/15">
        <BrainCircuit className="size-[18px]" aria-hidden="true" />
      </span>
      {!compact ? (
        <span className="leading-none">
          <span className="block text-[10px] font-bold tracking-[0.2em] text-[#61d4cb] uppercase">
            Blend
          </span>
          <span className="mt-1 block text-sm font-semibold tracking-tight">Knowledge Brain</span>
        </span>
      ) : null}
    </Link>
  )
}
