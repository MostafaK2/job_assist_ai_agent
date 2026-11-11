"use client";

import { useState } from "react";
import { TextArea, TextField } from "@/components/ui/Field";

/**
 * A list of editable entries (jobs, schools...) that can be added and removed, up to `max`.
 *
 * fields: [{ key, label, placeholder?, hint?, wide?, type?: "text" | "lines" }]
 *   "lines" = a text box where each line is one item (stored as an array).
 * errors: { "<entry _key>.<field key>": "message" }
 */
export default function EntryList({
  title, itemLabel, itemLabelPlural, items, onChange, fields, makeEmpty, max, errors = {}, emptyText,
}) {
  const [newKey, setNewKey] = useState(null); // focus the first field of a just-added entry

  function update(key, field, value) {
    onChange(items.map((item) => (item._key === key ? { ...item, [field]: value } : item)));
  }

  function add() {
    if (items.length >= max) return;
    const entry = makeEmpty();
    setNewKey(entry._key);
    onChange([...items, entry]);
  }

  function remove(key) {
    onChange(items.filter((item) => item._key !== key));
  }

  const atLimit = items.length >= max;

  return (
    <section className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-bold">{title}</h2>
        <span className="text-sm text-muted">{items.length} of {max}</span>
      </div>

      {items.length === 0 && <p className="text-muted">{emptyText}</p>}

      {items.map((item, index) => (
        <div
          key={item._key}
          role="group"
          aria-label={`${itemLabel} ${index + 1}`}
          className="rounded-lg border border-line bg-surface p-4"
        >
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-muted">
              {itemLabel} {index + 1}
            </span>
            <button
              type="button"
              onClick={() => remove(item._key)}
              className="text-sm text-stop underline"
              aria-label={`Remove ${itemLabel.toLowerCase()} ${index + 1}`}
            >
              Remove
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {fields.map((f, fieldIndex) => {
              const error = errors[`${item._key}.${f.key}`];
              const common = {
                label: f.label,
                placeholder: f.placeholder,
                hint: f.hint,
                error,
                autoFocus: item._key === newKey && fieldIndex === 0,
              };
              return (
                <div key={f.key} className={f.wide ? "sm:col-span-2" : ""}>
                  {f.type === "lines" ? (
                    <TextArea
                      {...common}
                      value={(item[f.key] || []).join("\n")}
                      onChange={(v) => update(item._key, f.key, v.split("\n"))}
                    />
                  ) : (
                    <TextField
                      {...common}
                      value={item[f.key]}
                      onChange={(v) => update(item._key, f.key, v)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {atLimit ? (
        <p className="text-sm text-muted">You can add up to {max} {itemLabelPlural}.</p>
      ) : (
        <button
          type="button"
          onClick={add}
          className="rounded-md border border-dashed border-ink/40 bg-surface px-4 py-2 text-sm font-medium"
        >
          Add {itemLabel.toLowerCase()}
        </button>
      )}
    </section>
  );
}