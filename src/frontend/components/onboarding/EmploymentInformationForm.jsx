"use client";

import { useState } from "react";
import { ChoiceGroup } from "@/components/ui/Field";
import { validateEmployment } from "@/lib/validate";

const YES_NO = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
];
const YES_NO_DECLINE = [...YES_NO, { value: "decline", label: "Prefer not to say" }];

const WORK_QUESTIONS = [
  { key: "authorized_us", legend: "Are you authorized to work in the US?" },
  { key: "authorized_canada", legend: "Are you authorized to work in Canada?" },
  { key: "authorized_uk", legend: "Are you authorized to work in the United Kingdom?" },
  { key: "needs_sponsorship", legend: "Will you now or in the future require sponsorship for employment visa status?" },
];

const GENDER = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "non_binary", label: "Non-binary" },
  { value: "decline", label: "Prefer not to say" },
];

const ETHNICITY = [
  { value: "american_indian_alaska_native", label: "American Indian or Alaska Native" },
  { value: "black", label: "Black or African American" },
  { value: "east_asian", label: "East Asian" },
  { value: "hispanic_latino", label: "Hispanic or Latino" },
  { value: "middle_eastern_north_african", label: "Middle Eastern or North African" },
  { value: "native_hawaiian_pacific_islander", label: "Native Hawaiian or Pacific Islander" },
  { value: "south_asian", label: "South Asian" },
  { value: "southeast_asian", label: "Southeast Asian" },
  { value: "white", label: "White" },
  { value: "two_or_more", label: "Two or more races" },
  { value: "decline", label: "Prefer not to say" },
];

const SELF_ID_QUESTIONS = [
  { key: "disability", legend: "Do you have a disability?" },
  { key: "lgbtq", legend: "Do you identify as LGBTQ+?" },
  { key: "veteran", legend: "Are you a veteran?" },
];

export default function EmploymentInformationForm({ initial, onBack, onDone }) {
  const [info, setInfo] = useState(initial);
  const [errors, setErrors] = useState({});

  // Save the answer and clear that question's error right away.
  const set = (key) => (value) => {
    setInfo((i) => ({ ...i, [key]: value }));
    setErrors(({ [key]: _cleared, ...rest }) => rest);
  };

  function handleSubmit(e) {
    e.preventDefault();
    const found = validateEmployment(info);
    setErrors(found);
    if (Object.keys(found).length === 0) onDone(info);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-10">
      <p className="text-muted">
        Most applications ask these questions. Answer them once here and the agent will fill them in for you.
      </p>

      <section className="space-y-6">
        <h2 className="text-lg font-bold">Work authorization</h2>
        {WORK_QUESTIONS.map((q) => (
          <ChoiceGroup
            key={q.key}
            legend={q.legend}
            options={YES_NO}
            value={info[q.key]}
            onChange={set(q.key)}
            error={errors[q.key]}
          />
        ))}
      </section>

      <section className="space-y-6">
        <div>
          <h2 className="text-lg font-bold">Voluntary self-identification</h2>
          <p className="mt-1 text-sm text-muted">
            Employers ask these for equal-opportunity reporting, and answering is voluntary.
            &ldquo;Prefer not to say&rdquo; is always a valid answer.
          </p>
        </div>

        <ChoiceGroup legend="What is your gender?" options={GENDER} value={info.gender} onChange={set("gender")} error={errors.gender} />

        <div>
          <label htmlFor="ethnicity" className="block text-sm font-medium">What is your ethnicity?</label>
          <select
            id="ethnicity"
            value={info.ethnicity ?? ""}
            onChange={(e) => set("ethnicity")(e.target.value || null)}
            aria-invalid={Boolean(errors.ethnicity)}
            className={`mt-1 w-full max-w-sm rounded-md border bg-surface px-3 py-2 ${errors.ethnicity ? "border-stop" : "border-line"}`}
          >
            <option value="">Choose one</option>
            {ETHNICITY.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {errors.ethnicity && <p className="mt-1 text-sm text-stop">{errors.ethnicity}</p>}
        </div>

        {SELF_ID_QUESTIONS.map((q) => (
          <ChoiceGroup
            key={q.key}
            legend={q.legend}
            options={YES_NO_DECLINE}
            value={info[q.key]}
            onChange={set(q.key)}
            error={errors[q.key]}
          />
        ))}
      </section>

      <div className="flex gap-3">
        <button type="button" onClick={onBack} className="rounded-md border border-line bg-surface px-5 py-2.5 font-medium">
          Back
        </button>
        <button type="submit" className="rounded-md bg-ink px-5 py-2.5 font-medium text-white">
          Continue
        </button>
      </div>
    </form>
  );
}