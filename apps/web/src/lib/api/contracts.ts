import { z } from "zod"

const nonEmptyString = z.string().trim().min(1)

export const projectSummarySchema = z.object({
  id: nonEmptyString,
  name: nonEmptyString,
  client: nonEmptyString.nullable(),
  industry: nonEmptyString.nullable(),
  engagementType: nonEmptyString.nullable(),
  summary: nonEmptyString.nullable(),
  technologies: z.array(nonEmptyString),
  documentCount: z.number().int().nonnegative(),
  updatedAt: z.iso.datetime(),
})

export type ProjectSummary = z.infer<typeof projectSummarySchema>

export const dashboardSchema = z.object({
  totalProjects: z.number().int().nonnegative(),
  indexedDocuments: z.number().int().nonnegative(),
  identifiedExperts: z.number().int().nonnegative(),
  knowledgeCoverage: z.number().min(0).max(1),
  recentProjects: z.array(projectSummarySchema),
  topIndustries: z.array(
    z.object({
      name: nonEmptyString,
      projectCount: z.number().int().positive(),
    }),
  ),
  updatedAt: z.iso.datetime(),
})

export type Dashboard = z.infer<typeof dashboardSchema>

export const projectCatalogSchema = z.object({
  projects: z.array(projectSummarySchema),
  total: z.number().int().nonnegative(),
})

export type ProjectCatalog = z.infer<typeof projectCatalogSchema>

const artifactCitationSchema = z.object({
  sourceId: nonEmptyString,
  quote: nonEmptyString,
  sourceKind: nonEmptyString.nullable(),
  projectId: nonEmptyString.nullable(),
  documentId: nonEmptyString.nullable(),
  sectionSequence: z.number().int().positive().nullable(),
  filename: nonEmptyString.nullable(),
})

const artifactStatementSchema = z.object({
  text: nonEmptyString,
  citations: z.array(artifactCitationSchema),
})

export const businessArtifactSchema = z.object({
  artifactId: nonEmptyString,
  kind: z.enum(["proposal", "project_one_pager"]),
  sourceProjectIds: z.array(nonEmptyString).min(1),
  title: nonEmptyString,
  subtitle: nonEmptyString.nullable(),
  sections: z.array(
    z.object({
      key: nonEmptyString,
      heading: nonEmptyString,
      statements: z.array(artifactStatementSchema),
    }),
  ),
  status: z.literal("draft"),
  model: nonEmptyString,
  promptVersion: nonEmptyString,
  createdAt: z.iso.datetime(),
})

export type BusinessArtifact = z.infer<typeof businessArtifactSchema>

export type ProposalRequest = {
  requestId: string
  projectIds: string[]
  clientName: string
  audience: string
  opportunity: string
  objectives: string[]
  constraints: string[]
}

export type OnePagerRequest = {
  requestId: string
  projectId: string
  audience: string
}

const evidenceSchema = z.object({
  documentId: nonEmptyString,
  filename: nonEmptyString,
  sectionSequence: z.number().int().positive(),
  quote: nonEmptyString,
  pageNumber: z.number().int().positive().nullable(),
  slideNumber: z.number().int().positive().nullable(),
  heading: nonEmptyString.nullable(),
})

export const groundedClaimSchema = z.object({
  value: nonEmptyString,
  confidence: z.enum(["high", "medium", "low"]),
  evidence: z.array(evidenceSchema).min(1),
})

export type GroundedClaim = z.infer<typeof groundedClaimSchema>

export const projectDnaSchema = z.object({
  id: nonEmptyString,
  projectId: nonEmptyString,
  version: z.number().int().positive(),
  generatedAt: z.iso.datetime(),
  model: nonEmptyString,
  projectName: groundedClaimSchema.nullable(),
  clientName: groundedClaimSchema.nullable(),
  industry: groundedClaimSchema.nullable(),
  engagementType: groundedClaimSchema.nullable(),
  summary: groundedClaimSchema.nullable(),
  businessChallenges: z.array(groundedClaimSchema),
  useCases: z.array(groundedClaimSchema),
  capabilities: z.array(groundedClaimSchema),
  technologies: z.array(groundedClaimSchema),
  dataSources: z.array(groundedClaimSchema),
  cloudPlatforms: z.array(groundedClaimSchema),
  outcomes: z.array(groundedClaimSchema),
  differentiators: z.array(groundedClaimSchema),
  experts: z.array(groundedClaimSchema),
})

export type ProjectDna = z.infer<typeof projectDnaSchema>

const documentSchema = z.object({
  id: nonEmptyString,
  filename: nonEmptyString,
  format: z.enum(["pptx", "docx", "pdf", "markdown", "txt"]),
  sectionCount: z.number().int().nonnegative(),
  updatedAt: z.iso.datetime(),
})

export const projectDetailsSchema = projectSummarySchema.extend({
  challenge: nonEmptyString.nullable(),
  solution: nonEmptyString.nullable(),
  outcomes: z.array(nonEmptyString),
  capabilities: z.array(nonEmptyString),
  experts: z.array(
    z.object({
      id: nonEmptyString,
      name: nonEmptyString,
      role: nonEmptyString.nullable(),
    }),
  ),
  documents: z.array(documentSchema),
  dna: projectDnaSchema.nullable(),
})

export type ProjectDetails = z.infer<typeof projectDetailsSchema>

const citationSchema = z.object({
  citationId: nonEmptyString,
  projectId: nonEmptyString,
  documentId: nonEmptyString,
  filename: nonEmptyString,
  sectionSequence: z.number().int().positive(),
  quote: nonEmptyString,
  pageNumber: z.number().int().positive().nullable(),
  slideNumber: z.number().int().positive().nullable(),
  heading: nonEmptyString.nullable(),
})

const answerSchema = z.object({
  question: nonEmptyString,
  answerable: z.boolean(),
  answer: nonEmptyString.nullable(),
  claims: z.array(
    z.object({
      text: nonEmptyString,
      citationIds: z.array(nonEmptyString).min(1),
    }),
  ),
  citations: z.array(citationSchema),
  confidence: z.object({
    score: z.number().min(0).max(1),
    band: z.enum(["high", "medium", "low"]),
    breakdown: z.object({
      retrievalStrength: z.number().min(0).max(1),
      citationCoverage: z.number().min(0).max(1),
      sourceDiversity: z.number().min(0).max(1),
    }),
  }),
  reason: z.string().trim().min(1).nullable(),
})

export const searchResponseSchema = z.object({
  answer: answerSchema,
  relatedProjects: z.array(projectSummarySchema),
})

export type SearchResponse = z.infer<typeof searchResponseSchema>

const similaritySignalSchema = z.object({
  kind: nonEmptyString,
  value: nonEmptyString,
})

export const similarProjectsSchema = z.object({
  projects: z.array(
    z.object({
      projectId: nonEmptyString,
      displayName: nonEmptyString,
      score: z.number().min(-1).max(1),
      sharedSignals: z.array(similaritySignalSchema),
    }),
  ),
})

export type SimilarProjects = z.infer<typeof similarProjectsSchema>

export const expertSearchSchema = z.object({
  experts: z.array(
    z.object({
      expertId: nonEmptyString,
      name: nonEmptyString,
      score: z.number().min(0).max(1),
      projectIds: z.array(nonEmptyString),
      matchedSignals: z.array(similaritySignalSchema),
      evidence: z.array(
        z.object({
          documentId: nonEmptyString,
          sectionSequence: z.number().int().positive(),
          quote: nonEmptyString,
        }),
      ),
    }),
  ),
})

export type ExpertSearch = z.infer<typeof expertSearchSchema>
