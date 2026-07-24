import { AlertTriangle, DatabaseZap, SearchX } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

type StatusPanelProps = {
  kind: "error" | "empty" | "not-found"
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
}

const icons = {
  error: DatabaseZap,
  empty: SearchX,
  "not-found": AlertTriangle,
}

export function StatusPanel({
  kind,
  title,
  description,
  actionLabel,
  onAction,
}: StatusPanelProps) {
  const Icon = icons[kind]
  return (
    <Card className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-muted text-muted-foreground">
        <Icon className="size-5" aria-hidden="true" />
      </div>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
      {actionLabel && onAction ? (
        <Button className="mt-5" variant="outline" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </Card>
  )
}
