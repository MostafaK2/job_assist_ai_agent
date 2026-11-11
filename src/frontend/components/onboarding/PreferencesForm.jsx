"use client";

import { useState } from "react";
import { ChoiceGroup, TextField, Toggle } from "@/components/ui/Field";
import { splitList, validatePreferences } from "@/lib/validate";

const SENIORITY = [
  { value: "intern", label: "Internship" },
  { value: "entry", label: "Entry level" },
  { value: "mid", label: "Mid level" },
  { value: "senior", label: "Senior" },
  { value: "any", label: "Any" },
];
const WORK_STYLE = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
  { value: "any", label: "Any" },
];


export default function PreferencesForm({ suggestedRoles, initial, initialSettings, saving, error, onBack, onDone }) {
  const [prefs, setPrefs] = useState(initial);
  const [settings, setSettings] = useState(initialSettings);
  const [newRole, setNewRole] = useState("");
  const [locationsText, setLocationsText] = useState(initial.preferred_locations.join(", "));
  const [avoidText, setAvoidText] = useState(initial.companies_to_avoid.join(", "));
  const [salaryText, setSalaryText] = useState(initial.min_salary ? String(initial.min_salary) : "");
  const [errors, setErrors] = useState({});

  const set = (key) => (value) => setPrefs((p) => ({ ...p, [key]: value }));
  const hasRole = (role) => prefs.target_roles.some((r) => r.toLowerCase() === role.toLowerCase());

  function toggleRole(role) {
    setPrefs((p) => ({
      ...p,
      target_roles: hasRole(role)
        ? p.target_roles.filter((r) => r.toLowerCase() !== role.toLowerCase())
        : [...p.target_roles, role],
    }));
  }

  function addRole() {
    const role = newRole.trim();
    if (role && !hasRole(role)) setPrefs((p) => ({ ...p, target_roles: [...p.target_roles, role] }));
    setNewRole("");
  }

  const customRoles = prefs.target_roles.filter(
    (r) => !suggestedRoles.some((s) => s.toLowerCase() === r.toLowerCase()),
  );

  function handleSubmit(e) {
    e.preventDefault();
    const salary = salaryText.replace(/[^\d]/g, "");
    const cleaned = {
      ...prefs,
      preferred_locations: prefs.remote_preference === "remote" ? [] : splitList(locationsText),
      companies_to_avoid: splitList(avoidText),
      min_salary: salary ? Number(salary) : null,
    };
    const found = validatePreferences(cleaned);
    setErrors(found);
    if (Object.keys(found).length === 0) onDone(cleaned, settings);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-8">
      <section>
        <h2 className="text-lg font-bold">Which roles are you looking for?</h2>
        {suggestedRoles.length > 0 && (
          <p className="mt-1 text-sm text-muted">Suggested from your resume. Select all that fit.</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {[...suggestedRoles, ...customRoles].map((role) => (
            <button
              key={role}
              type="button"
              aria-pressed={hasRole(role)}
              onClick={() => toggleRole(role)}
              className={`rounded-full border px-4 py-1.5 text-sm ${
                hasRole(role) ? "border-ink bg-ink text-white" : "border-line bg-surface"
              }`}
            >
              {hasRole(role) ? "✓ " : ""}{role}
            </button>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            aria-label="Add another role"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRole(); } }}
            placeholder="Add another role"
            className="w-full max-w-xs rounded-md border border-line bg-surface px-3 py-2"
          />
          <button type="button" onClick={addRole} className="rounded-md border border-line bg-surface px-4 py-2">
            Add
          </button>
        </div>
        {errors.target_roles && <p className="mt-2 text-sm text-stop">{errors.target_roles}</p>}
      </section>

      <ChoiceGroup legend="Level" options={SENIORITY} value={prefs.seniority} onChange={set("seniority")} />
      <ChoiceGroup legend="Work style" options={WORK_STYLE} value={prefs.remote_preference} onChange={set("remote_preference")} />

      {prefs.remote_preference !== "remote" && (
        <TextField
          label="Locations"
          value={locationsText}
          onChange={setLocationsText}
          placeholder="New York, Boston"
          hint="Separate cities with commas. Leave empty for anywhere."
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Minimum yearly salary (optional)"
          inputMode="numeric"
          value={salaryText}
          onChange={setSalaryText}
          placeholder="85000"
          error={errors.min_salary}
        />
        <TextField
          label="Companies to avoid (optional)"
          value={avoidText}
          onChange={setAvoidText}
          placeholder="Separate with commas"
        />
      </div>

      <section className="space-y-4 rounded-lg border border-line bg-surface p-5">
        <h2 className="text-lg font-bold">How much should the agent do on its own?</h2>
        <Toggle
          label="Let me pick jobs before applying"
          description="The agent shows you matching jobs and waits for you to choose."
          checked={settings.review_jobs}
          onChange={(v) => setSettings((s) => ({ ...s, review_jobs: v }))}
        />
        <Toggle
          label="Let me approve answers before forms are filled"
          description="You read and edit every drafted answer first."
          checked={settings.review_submissions}
          onChange={(v) => setSettings((s) => ({ ...s, review_submissions: v }))}
        />
        {!settings.review_submissions && (
          <p role="note" className="rounded-md bg-highlight/30 p-3 text-sm">
            The agent will fill in forms without showing you the answers first. Salary, work
            authorization and self-identification questions always come from your profile, and the agent
            still stops before clicking Submit.
          </p>
        )}
      </section>

      {error && <p role="alert" className="text-stop">{error}</p>}

      <div className="flex gap-3">
        <button type="button" onClick={onBack} className="rounded-md border border-line bg-surface px-5 py-2.5 font-medium">
          Back
        </button>
        <button type="submit" disabled={saving} className="rounded-md bg-ink px-5 py-2.5 font-medium text-white disabled:opacity-60">
          {saving ? "Saving…" : "Save profile"}
        </button>
      </div>
    </form>
  );
}