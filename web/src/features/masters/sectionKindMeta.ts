/** Short labels + accent token for section rail (VMock-style category colors). */
export function sectionKindLabel(kind: string): string {
  const map: Record<string, string> = {
    profile: "Profile",
    experience_block: "Experience",
    education: "Education",
    skills: "Skills",
    projects: "Projects",
    other: "Other",
  };
  return map[kind] ?? kind.replace(/_/g, " ");
}

export function sectionKindAccent(kind: string): string {
  const safe = /^[\w-]+$/.test(kind) ? kind : "other";
  return safe;
}

export function sectionPreview(body: string, max = 72): string {
  const one = body.replace(/\s+/g, " ").trim();
  if (one.length <= max) return one || "—";
  return `${one.slice(0, max - 1)}…`;
}
