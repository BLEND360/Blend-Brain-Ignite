import { useQuery } from "@tanstack/react-query"
import {
  ArrowLeft,
  BrainCircuit,
  BriefcaseBusiness,
  Building2,
  CalendarClock,
  Database,
  FileCheck2,
  Lightbulb,
  Network,
  Sparkles,
  Target,
  Trophy,
  UserRound,
  Wrench,
} from "lucide-react"
import { Link, useParams } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusPanel } from "@/components/ui/status-panel"
import { ProjectNavigation } from "@/features/projects/project-navigation"
import type { GroundedClaim } from "@/lib/api/contracts"
import { projectDnaQuery } from "@/lib/api/queries"
import { useKnowledgeRepository } from "@/lib/api/repository-context"
import { formatDate } from "@/lib/utils"

export function ProjectDnaPage() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) {
    throw new Error("Project identifier is required")
  }
  const repository = useKnowledgeRepository()
  const dna = useQuery(projectDnaQuery(repository, projectId))

  if (dna.isPending) {
    return <DnaSkeleton />
  }
  if (dna.isError) {
    return (
      <StatusPanel
        kind="error"
        title="Project DNA is unavailable"
        description="The evidence-backed Project DNA record could not be loaded."
        actionLabel="Try again"
        onAction={() => void dna.refetch()}
      />
    )
  }

  const data = dna.data
  const title = data.projectName?.value ?? "Project DNA"
  return (
    <>
      <Button asChild variant="ghost" size="sm" className="mb-4 -ml-3">
        <Link to={`/projects/${encodeURIComponent(projectId)}`}>
          <ArrowLeft aria-hidden="true" /> Project overview
        </Link>
      </Button>
      <PageHeader
        eyebrow="Evidence-backed intelligence"
        title={title}
        description="A structured fingerprint of the engagement, extracted from project source material."
        actions={<Badge variant="success">DNA v{data.version}</Badge>}
      />
      <ProjectNavigation projectId={projectId} />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <IdentityCard label="Client" claim={data.clientName} icon={Building2} />
        <IdentityCard label="Industry" claim={data.industry} icon={BriefcaseBusiness} />
        <IdentityCard label="Engagement" claim={data.engagementType} icon={Network} />
        <Card className="p-5">
          <CalendarClock className="size-4 text-primary" aria-hidden="true" />
          <p className="mt-4 text-[11px] font-bold tracking-wide text-muted-foreground uppercase">Generated</p>
          <p className="mt-1 text-sm font-semibold">{formatDate(data.generatedAt)}</p>
          <p className="mt-1 truncate text-[11px] text-muted-foreground">{data.model}</p>
        </Card>
      </div>

      {data.summary ? (
        <Card className="mb-6 overflow-hidden border-primary/15 bg-gradient-to-r from-primary/4 to-teal-500/4">
          <CardHeader className="flex-row items-center gap-3">
            <div className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary">
              <BrainCircuit className="size-4" aria-hidden="true" />
            </div>
            <div>
              <CardTitle>DNA summary</CardTitle>
              <p className="text-xs text-muted-foreground">Grounded project narrative</p>
            </div>
          </CardHeader>
          <CardContent>
            <Claim claim={data.summary} prominent />
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <ClaimGroup title="Business challenges" icon={Target} claims={data.businessChallenges} />
        <ClaimGroup title="Use cases" icon={Lightbulb} claims={data.useCases} />
        <ClaimGroup title="Capabilities" icon={Sparkles} claims={data.capabilities} />
        <ClaimGroup title="Technologies" icon={Wrench} claims={data.technologies} />
        <ClaimGroup title="Data sources" icon={Database} claims={data.dataSources} />
        <ClaimGroup title="Cloud platforms" icon={Network} claims={data.cloudPlatforms} />
        <ClaimGroup title="Outcomes" icon={Trophy} claims={data.outcomes} />
        <ClaimGroup title="Differentiators" icon={FileCheck2} claims={data.differentiators} />
        <ClaimGroup title="Experts" icon={UserRound} claims={data.experts} />
      </div>
    </>
  )
}

function IdentityCard({
  label,
  claim,
  icon: Icon,
}: {
  label: string
  claim: GroundedClaim | null
  icon: typeof Building2
}) {
  return (
    <Card className="p-5">
      <Icon className="size-4 text-primary" aria-hidden="true" />
      <p className="mt-4 text-[11px] font-bold tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold">{claim?.value ?? "Not established"}</p>
      {claim ? <Confidence value={claim.confidence} /> : null}
    </Card>
  )
}

function ClaimGroup({
  title,
  icon: Icon,
  claims,
}: {
  title: string
  icon: typeof Target
  claims: GroundedClaim[]
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center gap-3">
        <div className="grid size-9 place-items-center rounded-xl bg-muted text-muted-foreground">
          <Icon className="size-4" aria-hidden="true" />
        </div>
        <div className="flex-1">
          <CardTitle>{title}</CardTitle>
          <p className="text-xs text-muted-foreground">
            {claims.length} grounded {claims.length === 1 ? "claim" : "claims"}
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {claims.length > 0 ? (
          claims.map((claim, index) => <Claim key={`${claim.value}-${index}`} claim={claim} />)
        ) : (
          <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            No supported claims were extracted.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function Claim({ claim, prominent = false }: { claim: GroundedClaim; prominent?: boolean }) {
  return (
    <div className={prominent ? "" : "rounded-xl border bg-background p-4"}>
      <div className="flex items-start justify-between gap-4">
        <p className={prominent ? "text-sm leading-7 sm:text-[15px]" : "text-sm leading-6"}>{claim.value}</p>
        <Confidence value={claim.confidence} />
      </div>
      <details className="mt-3 group">
        <summary className="cursor-pointer list-none text-[11px] font-semibold text-primary hover:underline focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:outline-none">
          View {claim.evidence.length} evidence {claim.evidence.length === 1 ? "source" : "sources"}
        </summary>
        <div className="mt-3 space-y-2">
          {claim.evidence.map((evidence, index) => (
            <blockquote key={`${evidence.documentId}-${evidence.sectionSequence}-${index}`} className="border-l-2 border-primary/20 pl-3 text-xs leading-5 text-muted-foreground">
              “{evidence.quote}”
              <footer className="mt-1 font-medium text-foreground/65">
                {evidence.filename} · {evidence.pageNumber ? `Page ${evidence.pageNumber}` : evidence.slideNumber ? `Slide ${evidence.slideNumber}` : `Section ${evidence.sectionSequence}`}
              </footer>
            </blockquote>
          ))}
        </div>
      </details>
    </div>
  )
}

function Confidence({ value }: { value: "high" | "medium" | "low" }) {
  const variant = value === "high" ? "success" : value === "medium" ? "warning" : "neutral"
  return (
    <Badge className="shrink-0 capitalize" variant={variant}>
      {value}
    </Badge>
  )
}

function DnaSkeleton() {
  return (
    <div aria-label="Loading Project DNA" aria-busy="true">
      <Skeleton className="h-24 w-2xl max-w-full" />
      <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-32 rounded-2xl" />)}
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-72 rounded-2xl" />)}
      </div>
    </div>
  )
}
