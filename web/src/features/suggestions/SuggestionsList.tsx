import type { ChangeLogEntry } from "../../lib/types";

interface SuggestionsListProps {
  entries: ChangeLogEntry[];
}

export function SuggestionsList({ entries }: SuggestionsListProps) {
  if (entries.length === 0) {
    return <p className="muted">No suggestions were returned for this run.</p>;
  }

  return (
    <div className="list">
      {entries.map((entry) => (
        <article className="card" key={`${entry.bullet_id}-${entry.action}`}>
          <div className="row spread">
            <strong>{entry.section}</strong>
            <span className="pill">{entry.action}</span>
          </div>
          <p>
            <strong>Original:</strong> {entry.original_text}
          </p>
          {entry.new_text ? (
            <p>
              <strong>Suggested:</strong> {entry.new_text}
            </p>
          ) : null}
          {entry.rationale ? (
            <p>
              <strong>Rationale:</strong> {entry.rationale}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}
