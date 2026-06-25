export type SectionKind =
  | "profile"
  | "experience_block"
  | "education"
  | "skills"
  | "projects"
  | "other";

export interface SectionProposal {
  title: string;
  kind: SectionKind | string;
  body_text: string;
  start_para: number;
  end_para: number;
  role_label?: string;
  employer_line?: string;
  title_line?: string;
  date_line?: string;
  custom_kind_name?: string;
}

export interface ImportMasterResponse {
  source_filename: string;
  alias?: string | null;
  sections: SectionProposal[];
  section_kinds: string[];
}

export interface FinalizeMasterRequest {
  source_filename: string;
  sections: SectionProposal[];
  overwrite?: boolean;
}

export interface MasterSummary {
  master_id: string;
  source_file: string;
  source_docx: string;
  source_pdf: string;
  json_path: string;
  template_config_path: string;
}

export interface MasterDetail {
  summary: MasterSummary;
  payload: Record<string, unknown>;
}

export interface TailorRunOptions {
  model_name: string;
  company_name: string;
  job_title: string;
  quick_mode: boolean;
  include_cover_letter: boolean;
  include_ats: boolean;
  include_qa: boolean;
  allow_experience_rewrites: boolean;
  allow_education_rewrites: boolean;
  max_pages: number;
}

export interface Selection {
  bullet_id: string;
  section: string;
  action: string;
  original_text: string;
  new_text?: string | null;
  rewrite_rationale?: string | null;
  relevance_score: number;
  jd_requirements_addressed: string[];
}

export interface ChangeLogEntry {
  bullet_id: string;
  section: string;
  action: string;
  original_text: string;
  new_text?: string | null;
  rationale: string;
  jd_requirements_addressed: string[];
}

export interface TailoringResultPayload {
  canonical_cv: Record<string, unknown>;
  jd_analysis: Record<string, unknown>;
  tailored_output: {
    profile_selections: Selection[];
    skills_to_highlight: string[];
    experience_selections: Selection[];
    project_selections: Selection[];
    education_selections: Selection[];
    summary_section?: string | null;
  };
  change_log: {
    entries: ChangeLogEntry[];
    total_bullets_considered: number;
    total_bullets_changed: number;
    total_bullets_rewritten: number;
    total_bullets_deselected: number;
  };
  qa_report: {
    matching_rate_score: number;
    factual_support_passed: boolean;
    keyword_coverage_pct: number;
    style_issues: string[];
    unsupported_claims: string[];
    section_length_ok: boolean;
    key_pain_points: string[];
    strong_points: string[];
    feedback: string;
  };
  ats_report: {
    jd_keywords: string[];
    covered_keywords: string[];
    gap_keywords: string[];
    added_by_tailoring: string[];
    coverage_pct: number;
  };
  page_budget?: Record<string, unknown>;
  layout_validation?: {
    max_pages?: number;
    page_count?: number | null;
    layout_passed?: boolean | null;
    validation_method?: string;
    notes?: string[];
  };
  artifacts?: ExportArtifactMetadata[];
  approval_status?: string;
  cover_letter: string;
}

export interface ExportArtifactMetadata {
  artifact_id: string;
  kind?: string;
  path?: string;
  page_count?: number | null;
  layout_passed?: boolean | null;
  html_path?: string | null;
  ats_parse_passed?: boolean | null;
  ats_parse_notes?: string[];
}

export interface ExportMetadata {
  cv_path: string;
  cover_letter_path: string;
  docx_path?: string | null;
  pdf_path?: string | null;
  html_path?: string | null;
  page_count?: number | null;
  layout_passed?: boolean | null;
  ats_parse_passed?: boolean | null;
  ats_parse_notes?: string[];
  artifact_ids?: string[];
  docs_url?: string | null;
}

export interface TailorRunResponse {
  run_id: string;
  master_id: string;
  created_at: string;
  options: TailorRunOptions;
  result: TailoringResultPayload;
}

export interface RunSummary {
  run_id: string;
  master_id: string;
  created_at: string;
  model_name: string;
  company_name: string;
  job_title: string;
}

export interface RunDetailResponse {
  run_id: string;
  master_id: string;
  created_at: string;
  options: TailorRunOptions;
  result: TailoringResultPayload;
  exports?: ExportMetadata | null;
}

export interface ExportResponse extends ExportMetadata {
  run_id: string;
}

export type AiTaskKind =
  | "score_job"
  | "tailor_cv"
  | "render_cv"
  | "rerun_tailoring"
  | "gemini_interaction";

export type AiTaskStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface AiTaskRestoreTarget {
  path: string;
  state: Record<string, unknown>;
}

export interface AiTaskEvent {
  created_at: string;
  level: "info" | "warning" | "error";
  message: string;
}

export interface AiTaskRecord {
  task_id: string;
  kind: AiTaskKind;
  status: AiTaskStatus;
  title: string;
  related_label: string;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  input: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error?: string | null;
  events: AiTaskEvent[];
  restore?: AiTaskRestoreTarget | null;
  approval_required_before_apply: boolean;
}

export interface AiTaskListResponse {
  tasks: AiTaskRecord[];
  count: number;
}
