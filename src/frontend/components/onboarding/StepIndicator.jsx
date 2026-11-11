const STEPS = ["Upload resume", "Check details", "Employment information", "Preferences"];

export default function StepIndicator({ current }) {
  return (
    <ol className="mb-8 flex flex-wrap gap-x-6 gap-y-2 text-sm">
      {STEPS.map((label, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li key={label} aria-current={state === "current" ? "step" : undefined} className="flex items-center gap-2">
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                state === "done" ? "bg-go text-white" : state === "current" ? "bg-ink text-white" : "border border-line text-muted"
              }`}
            >
              {state === "done" ? "✓" : i + 1}
            </span>
            <span className={state === "todo" ? "text-muted" : "font-medium"}>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}