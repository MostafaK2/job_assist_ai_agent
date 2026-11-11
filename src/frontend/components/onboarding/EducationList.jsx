import EntryList from "@/components/onboarding/EntryList";
import { MAX_EDUCATION, emptyEducation } from "@/lib/entries";

const FIELDS = [
  { key: "school", label: "School", wide: true },
  { key: "degree", label: "Degree", placeholder: "B.S." },
  { key: "field", label: "Field of study", placeholder: "Computer Science" },
  { key: "graduation", label: "Graduation date", placeholder: "May 2026" },
];

export default function EducationList({ items, onChange, errors }) {
  return (
    <EntryList
      title="Education"
      itemLabel="School"
      itemLabelPlural="schools"
      items={items}
      onChange={onChange}
      fields={FIELDS}
      makeEmpty={emptyEducation}
      max={MAX_EDUCATION}
      errors={errors}
      emptyText="No education found on your resume."
    />
  );
}