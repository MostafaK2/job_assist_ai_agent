// Experience and education entries: limits, empty templates, and clean-up before saving.
// The backend enforces the same limits.

export const MAX_EXPERIENCE = 10;
export const MAX_EDUCATION = 5;
export const MAX_HIGHLIGHTS = 5;

let nextKey = 0;
/** Gives each entry a stable key so React keeps the right inputs when one is removed. */
export const withKey = (entry) => ({ ...entry, _key: `entry-${nextKey++}` });

export const emptyExperience = () =>
  withKey({ title: "", company: "", start: "", end: "", highlights: [] });

export const emptyEducation = () =>
  withKey({ school: "", degree: "", field: "", graduation: "" });

const clean = (value) => (typeof value === "string" ? value.trim() || null : value);

/** Removes the React key, trims text and drops empty highlight lines. */
export function cleanExperience(entries) {
  return entries.slice(0, MAX_EXPERIENCE).map(({ _key, ...job }) => ({
    title: job.title.trim(),
    company: job.company.trim(),
    start: clean(job.start),
    end: clean(job.end),
    highlights: (job.highlights || []).map((h) => h.trim()).filter(Boolean).slice(0, MAX_HIGHLIGHTS),
  }));
}

export function cleanEducation(entries) {
  return entries.slice(0, MAX_EDUCATION).map(({ _key, ...ed }) => ({
    school: ed.school.trim(),
    degree: clean(ed.degree),
    field: clean(ed.field),
    graduation: clean(ed.graduation),
  }));
}