export type JobRecommendation = "apply" | "skip" | "worth_20_minutes";

export interface ScoreJobInput {
  job_description: string;
  company_name?: string;
  job_title?: string;
  source_url?: string;
}

export interface ScoreJobOutput {
  job_id: string;
  match_score: number;
  recommendation: JobRecommendation;
  reasons: string[];
  concerns: string[];
  missing_keywords: string[];
  best_evidence_block_ids: string[];
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
