import type {
  Dashboard,
  ExpertSearch,
  ProjectDetails,
  ProjectDna,
  SearchResponse,
  SimilarProjects,
  BusinessArtifact,
  OnePagerRequest,
  ProposalRequest,
  ProjectCatalog,
} from "./contracts"

export type RequestOptions = {
  signal?: AbortSignal
}

export type KnowledgeRepository = {
  getDashboard: (options?: RequestOptions) => Promise<Dashboard>
  getProjects: (query?: string, options?: RequestOptions) => Promise<ProjectCatalog>
  search: (question: string, options?: RequestOptions) => Promise<SearchResponse>
  getProject: (projectId: string, options?: RequestOptions) => Promise<ProjectDetails>
  getProjectDna: (projectId: string, options?: RequestOptions) => Promise<ProjectDna>
  getSimilarProjects: (projectId: string, options?: RequestOptions) => Promise<SimilarProjects>
  findExperts: (query: string, options?: RequestOptions) => Promise<ExpertSearch>
  generateProposal: (request: ProposalRequest, options?: RequestOptions) => Promise<BusinessArtifact>
  generateOnePager: (request: OnePagerRequest, options?: RequestOptions) => Promise<BusinessArtifact>
  exportArtifactPdf: (artifact: BusinessArtifact, options?: RequestOptions) => Promise<Blob>
}
