import type {
  Dashboard,
  GroundedClaim,
  ProjectDetails,
  ProjectDna,
  ProjectSummary,
  SearchResponse,
} from "@/lib/api/contracts"

export const now = "2026-07-24T12:00:00Z"

export const claim: GroundedClaim = {
  value: "Reduced planning time by 30%",
  confidence: "high",
  evidence: [
    {
      documentId: "document-1",
      filename: "retail-forecasting.pdf",
      sectionSequence: 2,
      quote: "reduced planning time by 30%",
      pageNumber: 4,
      slideNumber: null,
      heading: "Outcomes",
    },
  ],
}

export const summary: ProjectSummary = {
  id: "project-1",
  name: "Retail Demand Forecasting",
  client: "Example Retailer",
  industry: "Retail",
  engagementType: "Data & AI",
  summary: "A demand forecasting platform for store planning.",
  technologies: ["Snowflake", "AWS", "Python"],
  documentCount: 3,
  updatedAt: now,
}

export const dna: ProjectDna = {
  id: "dna-1",
  projectId: "project-1",
  version: 1,
  generatedAt: now,
  model: "gpt-4.1-2025-04-14",
  projectName: { ...claim, value: summary.name },
  clientName: { ...claim, value: "Example Retailer" },
  industry: { ...claim, value: "Retail" },
  engagementType: { ...claim, value: "Data & AI" },
  summary: { ...claim, value: summary.summary ?? claim.value },
  businessChallenges: [{ ...claim, value: "Manual forecasting constrained planners" }],
  useCases: [{ ...claim, value: "Demand forecasting" }],
  capabilities: [{ ...claim, value: "Predictive analytics" }],
  technologies: [{ ...claim, value: "Snowflake" }],
  dataSources: [],
  cloudPlatforms: [{ ...claim, value: "AWS" }],
  outcomes: [claim],
  differentiators: [],
  experts: [{ ...claim, value: "Forecasting lead" }],
}

export const project: ProjectDetails = {
  ...summary,
  challenge: "Manual forecasts could not respond quickly to demand shifts.",
  solution: "A governed forecasting platform unified planning signals.",
  outcomes: [claim.value],
  capabilities: ["Predictive analytics"],
  experts: [{ id: "expert-1", name: "Blend Expert", role: "Data Science Lead" }],
  documents: [
    {
      id: "document-1",
      filename: "retail-forecasting.pdf",
      format: "pdf",
      sectionCount: 12,
      updatedAt: now,
    },
  ],
  dna,
}

export const dashboard: Dashboard = {
  totalProjects: 1248,
  indexedDocuments: 6412,
  identifiedExperts: 286,
  knowledgeCoverage: 0.78,
  recentProjects: [summary],
  topIndustries: [{ name: "Retail", projectCount: 42 }],
  updatedAt: now,
}

export const searchResponse: SearchResponse = {
  answer: {
    question: "What improved?",
    answerable: true,
    answer: "Planning time improved.",
    claims: [{ text: "Planning time was reduced by 30%.", citationIds: ["C1"] }],
    citations: [
      {
        citationId: "C1",
        projectId: "project-1",
        documentId: "document-1",
        filename: "retail-forecasting.pdf",
        sectionSequence: 2,
        quote: "reduced planning time by 30%",
        pageNumber: 4,
        slideNumber: null,
        heading: "Outcomes",
      },
    ],
    confidence: {
      score: 0.88,
      band: "high",
      breakdown: { retrievalStrength: 0.84, citationCoverage: 1, sourceDiversity: 1 },
    },
    reason: null,
  },
  relatedProjects: [summary],
}
