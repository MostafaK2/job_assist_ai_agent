"use client";

import { useState } from "react";
import EducationList from "@/components/onboarding/EducationList";
import ExperienceList from "@/components/onboarding/ExperienceList";
import { TextField } from "@/components/ui/Field";
import { MAX_EDUCATION, MAX_EXPERIENCE, cleanEducation, cleanExperience, withKey } from "@/lib/entries";
import { splitList, validateDetails } from "@/lib/validate";

/** "Jordan A. Rivera" -> { first: "Jordan", last: "A. Rivera" } */
function splitName(full) {
  const parts = (full || "").trim().split(/\s+/).filter(Boolean);
  return { first: parts[0] || "", last: parts.slice(1).join(" ") };
}

/** Adds https:// if missing; empty -> null. */
function normalizeUrl(value) {
  const v = value?.trim();
  if (!v) return null;
  return /^https?:\/\//i.test(v) ? v : `https://${v}`;
}

export default function DetailsForm({ resume, onBack, onDone }) {
  const [form, setForm] = useState(() => ({
    ...resume,
    // The resume reader gives one full name; the form asks for first and last separately.
    first_name: resume.first_name ?? splitName(resume.full_name).first,
    last_name: resume.last_name ?? splitName(resume.full_name).last,
    // Give every job and school a stable key (and respect the limits, even if the resume had more).
    experience: resume.experience.slice(0, MAX_EXPERIENCE).map(withKey),
    education: resume.education.slice(0, MAX_EDUCATION).map(withKey),
  }));
  const [skillsText, setSkillsText] = useState(resume.skills.join(", "));
  const [errors, setErrors] = useState({});
  // Remember which fields were empty on the resume, so they keep their "needs you" mark.
  // Only required fields (and LinkedIn) get the mark; optional fields like address stay quiet.
  const [missing] = useState(() => {
    const name = splitName(resume.full_name);
    return {
      first_name: !(resume.first_name ?? name.first),
      last_name: !(resume.last_name ?? name.last),
      email: !resume.email,
      phone: !resume.phone,
      location: !resume.location,
      linkedin_url: !resume.linkedin_url,
    };
  });

  // Update a field, and drop any error that this change fixed (new errors only appear on Continue).
  const set = (key) => (value) => {
    const next = { ...form, [key]: value };
    setForm(next);
    const stillWrong = validateDetails(next);
    setErrors((errs) => Object.fromEntries(Object.entries(errs).filter(([k]) => k in stillWrong)));
  };

  function handleSubmit(e) {
    e.preventDefault();
    const checked = {
      ...form,
      linkedin_url: normalizeUrl(form.linkedin_url),
      github_url: normalizeUrl(form.github_url),
      portfolio_url: normalizeUrl(form.portfolio_url),
    };

    const found = validateDetails(checked);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    onDone({
      ...checked,
      // Keep full_name too: the backend and the agent still use it.
      full_name: [checked.first_name, checked.last_name].map((n) => n.trim()).filter(Boolean).join(" "),
      skills: splitList(skillsText),
      experience: cleanExperience(checked.experience),
      education: cleanEducation(checked.education),
    });
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-8">
      <p className="text-muted">
        Here&apos;s what we found. Fix anything that&apos;s wrong and fill in the
        <span className="mx-1 bg-highlight/60 px-1 text-ink">highlighted</span>
        fields.
      </p>

      <section className="space-y-4">
        <h2 className="text-lg font-bold">Personal information</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="First name" value={form.first_name} onChange={set("first_name")} error={errors.first_name} missing={missing.first_name} autoComplete="given-name" />
          <TextField label="Last name" value={form.last_name} onChange={set("last_name")} error={errors.last_name} missing={missing.last_name} autoComplete="family-name" />
          <TextField label="Preferred name (optional)" value={form.preferred_name} onChange={set("preferred_name")} autoComplete="nickname" hint="What you'd like to be called, if different." />
          <TextField label="Suffix (optional)" value={form.suffix_name} onChange={set("suffix_name")} autoComplete="honorific-suffix" placeholder="Jr., III" />
          <TextField label="Email" type="email" value={form.email} onChange={set("email")} error={errors.email} missing={missing.email} autoComplete="email" />
          <TextField label="Phone" type="tel" value={form.phone} onChange={set("phone")} error={errors.phone} missing={missing.phone} autoComplete="tel" />
          <TextField
            label="Date of birth (optional)"
            type="date"
            value={form.date_of_birth}
            onChange={set("date_of_birth")}
            error={errors.date_of_birth}
            autoComplete="bday"
            hint="Only used if an application asks for it."
          />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-bold">Location</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <TextField label="Street address (optional)" value={form.address} onChange={set("address")} autoComplete="address-line1" />
          </div>
          <TextField label="Address line 2 (optional)" value={form.address_line_2} onChange={set("address_line_2")} autoComplete="address-line2" placeholder="Apartment, suite, unit" />
          <TextField label="Address line 3 (optional)" value={form.address_line_3} onChange={set("address_line_3")} autoComplete="address-line3" />
          <TextField label="City and state" value={form.location} onChange={set("location")} error={errors.location} missing={missing.location} hint="Used to match jobs near you." />
          <TextField label="Postal code (optional)" value={form.postal_code} onChange={set("postal_code")} error={errors.postal_code} autoComplete="postal-code" />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-bold">Links</h2>
        <TextField
          label="LinkedIn (optional)"
          value={form.linkedin_url}
          onChange={set("linkedin_url")}
          error={errors.linkedin_url}
          missing={missing.linkedin_url}
          placeholder="linkedin.com/in/your-name"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="GitHub (optional)" value={form.github_url} onChange={set("github_url")} error={errors.github_url} placeholder="github.com/your-name" />
          <TextField label="Website or portfolio (optional)" value={form.portfolio_url} onChange={set("portfolio_url")} error={errors.portfolio_url} placeholder="yourname.dev" />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-bold">Skills</h2>
        <TextField label="Skills" value={skillsText} onChange={setSkillsText} hint="Separate skills with commas." />
      </section>

      <ExperienceList items={form.experience} onChange={set("experience")} errors={errors} />

      <EducationList items={form.education} onChange={set("education")} errors={errors} />

      <div className="flex gap-3">
        <button type="button" onClick={onBack} className="rounded-md border border-line bg-surface px-5 py-2.5 font-medium">
          Upload a different resume
        </button>
        <button type="submit" className="rounded-md bg-ink px-5 py-2.5 font-medium text-white">
          Continue
        </button>
      </div>
    </form>
  );
}