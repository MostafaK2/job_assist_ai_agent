"use client";

import { useId } from "react";

/** A labelled multi-line text box. */
export function TextArea({ label, value, onChange, error, hint, rows = 3, ...props }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">{label}</label>
      <textarea
        id={id}
        rows={rows}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`mt-1 w-full rounded-md border bg-surface px-3 py-2 ${error ? "border-stop" : "border-line"}`}
        {...props}
      />
      {hint && !error && <p className="mt-1 text-sm text-muted">{hint}</p>}
      {error && <p id={`${id}-error`} className="mt-1 text-sm text-stop">{error}</p>}
    </div>
  );
}

/** A labelled text input. `missing` adds the yellow "needs you" mark. */
export function TextField({ label, value, onChange, error, hint, missing, type = "text", ...props }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        <span className={missing ? "bg-highlight/60 px-1" : ""}>{label}</span>
        {missing && <span className="ml-2 font-normal text-muted">Not on your resume</span>}
      </label>
      <input
        id={id}
        type={type}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`mt-1 w-full rounded-md border bg-surface px-3 py-2 ${error ? "border-stop" : "border-line"}`}
        {...props}
      />
      {hint && !error && <p className="mt-1 text-sm text-muted">{hint}</p>}
      {error && <p id={`${id}-error`} className="mt-1 text-sm text-stop">{error}</p>}
    </div>
  );
}

/** Radio buttons that look like a row of pills. options = [{ value, label }] */
export function ChoiceGroup({ legend, options, value, onChange, error }) {
  const name = useId();
  return (
    <fieldset>
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((o) => (
          <label
            key={o.value}
            className={`cursor-pointer rounded-full border px-4 py-1.5 text-sm has-[:focus-visible]:outline-2 ${
              value === o.value ? "border-ink bg-ink text-white" : "border-line bg-surface"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="sr-only"
            />
            {o.label}
          </label>
        ))}
      </div>
      {error && <p className="mt-1 text-sm text-stop">{error}</p>}
    </fieldset>
  );
}

/** On/off setting with an explanation. */
export function Toggle({ label, description, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 accent-ink"
      />
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-sm text-muted">{description}</span>
      </span>
    </label>
  );
}