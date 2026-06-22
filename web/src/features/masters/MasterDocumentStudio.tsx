import { useCallback, useEffect, useRef, useState } from "react";
import { sectionKindAccent, sectionKindLabel, sectionPreview } from "./sectionKindMeta";
import type { SectionProposal } from "../../lib/types";

export interface MasterDocumentStudioProps {
  sections: SectionProposal[];
  sectionKinds: readonly string[];
  onChange: (next: SectionProposal[]) => void;
  /** Shown in rail header, e.g. "Review" or master id */
  documentLabel: string;
}

export function MasterDocumentStudio({ sections, sectionKinds, onChange, documentLabel }: MasterDocumentStudioProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const headingRef = useRef<HTMLInputElement>(null);
  const activeRailBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setSelectedIndex((i) => {
      if (sections.length === 0) return 0;
      return Math.min(i, sections.length - 1);
    });
  }, [sections.length]);

  const section = sections[selectedIndex];
  const accent = section ? sectionKindAccent(String(section.kind)) : "other";

  const patchSection = useCallback(
    (index: number, partial: Partial<SectionProposal>) => {
      const copy = sections.slice();
      const updated = { ...copy[index], ...partial };
      if (
        updated.kind === "experience_block" ||
        updated.kind === "education" ||
        updated.kind === "projects"
      ) {
        if ("title_line" in partial) {
          updated.title = partial.title_line || "";
        } else if ("kind" in partial && !updated.title_line) {
          updated.title_line = updated.title;
        }
      }
      copy[index] = updated;
      onChange(copy);
    },
    [sections, onChange],
  );

  const insertSectionAt = useCallback(
    (atIndex: number) => {
      const blank: SectionProposal = {
        title: "New section",
        kind: "other",
        body_text: "",
        start_para: 0,
        end_para: 0,
        role_label: "",
        employer_line: "",
        title_line: "",
        date_line: "",
        custom_kind_name: "",
      };
      const next = [...sections.slice(0, atIndex), blank, ...sections.slice(atIndex)];
      onChange(next);
      setSelectedIndex(atIndex);
    },
    [sections, onChange],
  );

  useEffect(() => {
    headingRef.current?.focus();
    activeRailBtnRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedIndex]);

  const onRailKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, sections.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      }
    },
    [sections.length],
  );

  if (sections.length === 0) {
    return (
      <div className="docStudio docStudio--empty">
        <p className="muted">No sections yet. Import a document to detect structure.</p>
      </div>
    );
  }

  if (!section) {
    return null;
  }

  return (
    <div className="docStudio">
      <aside className="docStudioRail" tabIndex={0} onKeyDown={onRailKeyDown} aria-label="Section structure">
        <div className="docStudioRailHead">
          <span className="docStudioRailTitle">Structure</span>
          <span className="docStudioRailSub muted">{documentLabel}</span>
        </div>
        <p className="docStudioRailHint muted">
          Click a block to edit. Hover between blocks for <strong>+</strong> to insert. Use ↑ ↓ while this column is focused.
        </p>
        <div className="docStudioRailList" role="list">
          <div className="docStudioRailInsert" role="presentation">
            <button
              type="button"
              className="docStudioRailInsertBtn"
              aria-label="Add section at the beginning"
              title="Add section here"
              onClick={(e) => {
                e.stopPropagation();
                insertSectionAt(0);
              }}
            >
              +
            </button>
          </div>
          {sections.map((s, i) => {
            const active = i === selectedIndex;
            const ac = sectionKindAccent(String(s.kind));
            return (
              <div key={`rail-block-${i}`} className="docStudioRailBlock" role="presentation">
                <div role="listitem">
                  <button
                    type="button"
                    id={`sec-${i}`}
                    ref={active ? activeRailBtnRef : undefined}
                    aria-current={active ? "true" : undefined}
                    className={`docStudioRailItem ${active ? "is-active" : ""}`}
                    onClick={() => setSelectedIndex(i)}
                  >
                    <span className={`docStudioKindBar docStudioKindBar--${ac}`} aria-hidden />
                    <span className="docStudioRailItemBody">
                      <span className="docStudioRailKind">{sectionKindLabel(String(s.kind))}</span>
                      <span className="docStudioRailHeading">{s.title || "Untitled section"}</span>
                      <span className="docStudioRailPreview muted">{sectionPreview(s.body_text)}</span>
                    </span>
                  </button>
                </div>
                <div className="docStudioRailInsert" role="presentation">
                  <button
                    type="button"
                    className="docStudioRailInsertBtn"
                    aria-label={`Add section after “${(s.title || "section").slice(0, 48)}”`}
                    title="Add section here"
                    onClick={(e) => {
                      e.stopPropagation();
                      insertSectionAt(i + 1);
                    }}
                  >
                    +
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </aside>

      <div className="docStudioDesk">
        <div className="docStudioDeskInner">
          <div className="docStudioToolbar">
            <span className="docStudioToolbarMeta muted">
              Section {selectedIndex + 1} of {sections.length}
            </span>
            <label className="docStudioToolbarKind">
              <span className="muted">Type</span>
              <select
                value={String(section.kind)}
                onChange={(e) => patchSection(selectedIndex, { kind: e.target.value })}
              >
                {[...new Set([...sectionKinds, String(section.kind)])].map((k) => (
                  <option key={k} value={k}>
                    {sectionKindLabel(k)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <article className={`docStudioPage docStudioPage--accent-${accent}`} aria-label="Document page">
            <div className="docStudioRuler" aria-hidden />
            {section.kind !== "experience_block" && section.kind !== "education" && section.kind !== "projects" ? (
              <label className="docStudioField docStudioField--flush">
                <span className="docStudioFieldLabel">Heading</span>
                <input
                  ref={headingRef}
                  className="docStudioTitleInput"
                  value={section.title}
                  onChange={(e) => patchSection(selectedIndex, { title: e.target.value })}
                  placeholder="Section heading as it appears on the CV"
                />
              </label>
            ) : null}

            {section.kind === "experience_block" || section.kind === "education" || section.kind === "projects" ? (
              <div className="docStudioMetaGrid">
                {section.kind === "education" ? (
                  <label className="docStudioField">
                    <span className="docStudioFieldLabel">
                      GPA / Honors
                    </span>
                    <input
                      value={section.role_label ?? ""}
                      onChange={(e) => patchSection(selectedIndex, { role_label: e.target.value })}
                      placeholder="GPA: 3.53 / 4.0 or honors"
                    />
                  </label>
                ) : null}
                <label className="docStudioField">
                  <span className="docStudioFieldLabel">
                    {section.kind === "education" ? "Institution" : section.kind === "projects" ? "Description / Context" : "Employer"}
                  </span>
                  <input
                    value={section.employer_line ?? ""}
                    onChange={(e) => patchSection(selectedIndex, { employer_line: e.target.value })}
                    placeholder={section.kind === "education" ? "University / College" : section.kind === "projects" ? "e.g. Interactive Platform" : "Company — City"}
                  />
                </label>
                <label className="docStudioField">
                  <span className="docStudioFieldLabel">
                    {section.kind === "education" ? "Degree / Program" : section.kind === "projects" ? "Project Title" : "Title line"}
                  </span>
                  <input
                    value={section.title_line ?? ""}
                    onChange={(e) => patchSection(selectedIndex, { title_line: e.target.value })}
                    placeholder={section.kind === "education" ? "e.g. Bachelor of Science" : section.kind === "projects" ? "e.g. ApplAI" : "Official job title"}
                  />
                </label>
                <label className="docStudioField">
                  <span className="docStudioFieldLabel">Dates</span>
                  <input
                    value={section.date_line ?? ""}
                    onChange={(e) => patchSection(selectedIndex, { date_line: e.target.value })}
                    placeholder={section.kind === "projects" ? "e.g. May 2026" : "2022 — Present"}
                  />
                </label>
              </div>
            ) : null}

            <label className="docStudioField docStudioField--grow">
              <span className="docStudioFieldLabel">Body</span>
              <textarea
                className="docStudioBody"
                value={section.body_text}
                onChange={(e) => patchSection(selectedIndex, { body_text: e.target.value })}
                placeholder="Bullets and paragraphs for this section…"
                spellCheck
              />
            </label>
          </article>
        </div>
      </div>
    </div>
  );
}
