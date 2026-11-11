import EntryList from "@/components/onboarding/EntryList";
import { MAX_EXPERIENCE, MAX_HIGHLIGHTS, emptyExperience } from "@/lib/entries";

const FIELDS = [
  { key: "title", label: "Job title" },
  { key: "company", label: "Company" },
  { key: "start", label: "Start date", placeholder: "Jun 2024" },
  { key: "end", label: "End date", placeholder: "Present", hint: "Leave empty if you still work here." },
  {
    key: "highlights",
    label: "What you did (optional)",
    type: "lines",
    wide: true,
    hint: `One achievement per line, up to ${MAX_HIGHLIGHTS}. The agent uses these when writing your answers.`,
  },
];

export default function ExperienceList({ items, onChange, errors }) {
  return (
    <EntryList
      title="Experience"
      itemLabel="Job"
      itemLabelPlural="jobs"
      items={items}
      onChange={onChange}
      fields={FIELDS}
      makeEmpty={emptyExperience}
      max={MAX_EXPERIENCE}
      errors={errors}
      emptyText="No jobs found on your resume. Add any jobs, internships or volunteer roles."
    />
  );
}