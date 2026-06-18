import type { TailorRunOptions } from "../../lib/types";

interface TailorOptionsFormProps {
  value: TailorRunOptions;
  onChange: (next: TailorRunOptions) => void;
}

export function TailorOptionsForm({ value, onChange }: TailorOptionsFormProps) {
  return (
    <div className="card">
      <h3>Tailoring options</h3>
      <div className="grid2">
        <label className="field">
          <span>Model</span>
          <input
            value={value.model_name}
            onChange={(event) => onChange({ ...value, model_name: event.target.value })}
            placeholder="gemini-2.5-flash"
          />
        </label>
        <label className="field">
          <span>Max pages</span>
          <input
            type="number"
            min={1}
            max={3}
            value={value.max_pages}
            onChange={(event) => onChange({ ...value, max_pages: Number(event.target.value) || 2 })}
          />
        </label>
      </div>
      <div className="grid2">
        <label className="field checkbox">
          <input
            type="checkbox"
            checked={value.quick_mode}
            onChange={(event) => onChange({ ...value, quick_mode: event.target.checked })}
          />
          Quick mode
        </label>
        <label className="field checkbox">
          <input
            type="checkbox"
            checked={value.include_cover_letter}
            onChange={(event) => onChange({ ...value, include_cover_letter: event.target.checked })}
          />
          Include cover letter
        </label>
      </div>
      <div className="grid2">
        <label className="field checkbox">
          <input
            type="checkbox"
            checked={value.include_ats}
            onChange={(event) => onChange({ ...value, include_ats: event.target.checked })}
          />
          Include ATS
        </label>
        <label className="field checkbox">
          <input
            type="checkbox"
            checked={value.include_qa}
            onChange={(event) => onChange({ ...value, include_qa: event.target.checked })}
          />
          Include QA
        </label>
      </div>
      <div className="grid2">
        <label className="field checkbox">
          <input
            type="checkbox"
            checked={value.allow_experience_rewrites}
            onChange={(event) => onChange({ ...value, allow_experience_rewrites: event.target.checked })}
          />
          Allow experience rewrites
        </label>
        <label className="field checkbox">
          <input
            type="checkbox"
            checked={value.allow_education_rewrites}
            onChange={(event) => onChange({ ...value, allow_education_rewrites: event.target.checked })}
          />
          Allow education rewrites
        </label>
      </div>
    </div>
  );
}
