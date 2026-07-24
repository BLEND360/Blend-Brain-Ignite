import { ArrowUpRight, Building2, FileText } from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import type { ProjectSummary } from "@/lib/api/contracts"
import { formatDate } from "@/lib/utils"

type ProjectCardProps = {
  project: ProjectSummary
}

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Card className="group flex h-full flex-col overflow-hidden transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:border-primary/20 hover:shadow-lg">
      <Link
        to={`/projects/${encodeURIComponent(project.id)}`}
        className="flex h-full flex-col p-5 outline-none focus-visible:ring-2 focus-visible:ring-primary/30 sm:p-6"
      >
        <div className="mb-5 flex items-start justify-between gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-primary/8 text-primary">
            <Building2 className="size-[18px]" aria-hidden="true" />
          </div>
          <ArrowUpRight
            className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary"
            aria-hidden="true"
          />
        </div>
        <h3 className="line-clamp-2 text-base font-semibold tracking-tight">{project.name}</h3>
        <p className="mt-1 text-xs font-medium text-muted-foreground">
          {[project.client, project.industry].filter(Boolean).join(" · ") || "Internal project"}
        </p>
        {project.summary ? (
          <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted-foreground">
            {project.summary}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {project.technologies.slice(0, 3).map((technology) => (
            <Badge key={technology} variant="neutral">
              {technology}
            </Badge>
          ))}
        </div>
        <div className="mt-auto flex items-center justify-between border-t pt-5 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <FileText className="size-3.5" aria-hidden="true" />
            {project.documentCount} {project.documentCount === 1 ? "document" : "documents"}
          </span>
          <span>Updated {formatDate(project.updatedAt)}</span>
        </div>
      </Link>
    </Card>
  )
}
