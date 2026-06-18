export type JobRecommendation = "apply" | "skip" | "worth_20_minutes";

export interface ScoreJobInput {
  job_description: string;
  company_name?: string;
  job_title?: string;
  source_url?: string;
  save_draft?: boolean;
}

export interface ParsedJobDescription {
  responsibilities: string[];
  qualifications: string[];
  keywords: string[];
  seniority: string;
  domain: string;
  location_remote_hints: string[];
  effort_signals: string[];
}

export interface EvidenceMatch {
  evidence_block_id: string;
  score: number;
  matched_terms: string[];
}

export interface ScoreReport {
  match_score: number;
  recommendation: JobRecommendation;
  reasons: string[];
  concerns: string[];
  missing_keywords: string[];
  top_evidence_block_ids: string[];
  evidence_matches: EvidenceMatch[];
  keyword_coverage: number;
  role_preference_hits: string[];
  skill_category_hits: string[];
}

export interface ScoreJobOutput {
  job_id: string;
  company_name?: string | null;
  job_title?: string | null;
  source_url?: string | null;
  match_score: number;
  recommendation: JobRecommendation;
  reasons: string[];
  concerns: string[];
  missing_keywords: string[];
  best_evidence_block_ids: string[];
  top_evidence_block_ids: string[];
  parsed_jd_summary: ParsedJobDescription;
  score_report: ScoreReport;
  saved: boolean;
  job_record_path?: string | null;
}

export interface EvidenceBlock {
  block_id: string;
  kind: "profile" | "experience" | "project" | "education" | "skill" | "preference" | "approved_note";
  text: string;
  source_label: string;
  source_path?: string | null;
  provenance: string[];
  relevance_tags: string[];
  technologies: string[];
  skill_categories: string[];
  ats_keywords: string[];
  metrics: string[];
  priority: number;
  truth_constraints: string[];
  length_estimate: number;
}

export interface ExperienceRecord {
  experience_id: string;
  employer: string;
  role: string;
  start_date: string;
  end_date: string;
  location: string;
  evidence_block_ids: string[];
}

export interface ProjectRecord {
  project_id: string;
  title: string;
  summary: string;
  technologies: string[];
  links: string[];
  evidence_block_ids: string[];
  pr_asset_status: "not_started" | "draft" | "approved";
}

export interface SkillInventory {
  categories: Record<string, string[]>;
  aliases: Record<string, string[]>;
  role_relevance: Record<string, string[]>;
}

export interface CareerBrainProfile {
  schema_version: string;
  owner: string;
  source_masters: string[];
  role_preferences: {
    preferred_roles: string[];
    target_companies: string[];
    preferred_locations: string[];
    work_authorization_notes: string;
    avoid_roles: string[];
  };
  writing_preferences: {
    tone: string;
    max_pages: number;
    bullet_style: string;
    banned_claims: string[];
    preferred_terms: string[];
  };
  skills: SkillInventory;
  evidence_blocks: EvidenceBlock[];
  experiences: ExperienceRecord[];
  projects: ProjectRecord[];
  created_at: string;
  updated_at: string;
}

export interface TailoredExampleSection {
  heading: string;
  text: string;
}

export interface TailoredExample {
  example_id: string;
  source_pdf_path: string;
  role_label: string;
  pdf_title?: string | null;
  page_count: number;
  extracted_text: string;
  section_headings: string[];
  sections: TailoredExampleSection[];
  parse_confidence: number;
}

export interface TailoredExamplesOutput {
  examples: TailoredExample[];
  count: number;
}

export interface TailorCvInput {
  job_id: string;
  master_id: string;
  max_pages: number;
  mode: "quick" | "full";
}

export interface RenderCvInput {
  run_id: string;
  format: "docx" | "pdf" | "both";
  max_pages: number;
}

export interface SaveApplicationInput {
  job_id: string;
  run_id?: string;
  artifact_ids?: string[];
  status: "draft" | "ready_to_submit" | "submitted" | "rejected" | "interview" | "offer";
}

export interface ApproveArtifactInput {
  artifact_id: string;
  decision: "approved" | "rejected" | "needs_changes";
  notes?: string;
}
