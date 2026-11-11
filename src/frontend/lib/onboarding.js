import { apiFetch } from "@/lib/api";

// Set NEXT_PUBLIC_USE_MOCK=true in .env.local to try the UI before the backend API exists.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

export const MAX_RESUME_MB = 5;

/** Sends the PDF to the backend, which reads it with Gemini. Returns { upload_id, resume }. */
export async function uploadResume(file) {
  if (USE_MOCK) return mockUpload();
  const form = new FormData();
  form.append("file", file);
  return apiFetch("/api/onboarding/resume", { method: "POST", body: form });
}

/** Saves the confirmed details, preferences and review settings. */
export async function saveProfile({ uploadId, resume, employment, preferences, settings }) {
  if (USE_MOCK) {
    await wait(600);
    return { ok: true };
  }
  return apiFetch("/api/profile", {
    method: "PUT",
    body: { upload_id: uploadId, resume, employment, preferences, settings },
  });
}

export const DEFAULT_PREFERENCES = {
  target_roles: [],
  seniority: "any",
  remote_preference: "any",
  preferred_locations: [],
  min_salary: null,
  companies_to_avoid: [],
};

/** Asked on most applications. null = not answered yet; "decline" = prefer not to say. */
export const DEFAULT_EMPLOYMENT = {
  authorized_us: null,
  authorized_canada: null,
  authorized_uk: null,
  needs_sponsorship: null,
  gender: null,
  ethnicity: null,
  disability: null,
  lgbtq: null,
  veteran: null,
};

export const DEFAULT_SETTINGS = {
  review_jobs: true,          // I pick jobs before the agent applies
  review_submissions: true,   // I approve answers before forms are filled
};

// ---------- mock (no backend needed) ----------

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function mockUpload() {
  await wait(1200);
  return {
    upload_id: "mock-upload",
    resume: {
      full_name: "Jordan Rivera",
      email: "jordan.rivera@example.com",
      phone: null,            // missing on purpose, so the form asks for it
      location: "Newark, NJ",
      linkedin_url: null,
      github_url: "https://github.com/jrivera",
      portfolio_url: null,
      summary: "Computer science student who builds data-heavy web apps.",
      skills: ["Python", "SQL", "React", "FastAPI", "PostgreSQL"],
      experience: [
        { title: "Software Engineering Intern", company: "Brightline Logistics", start: "Jun 2025", end: "Aug 2025", highlights: [] },
        { title: "Teaching Assistant, Data Structures", company: "State University", start: "Jan 2025", end: "Present", highlights: [] },
      ],
      education: [{ school: "State University", degree: "B.S.", field: "Computer Science", graduation: "May 2026" }],
      suggested_roles: ["Backend Engineer", "Software Engineer", "Data Engineer"],
    },
  };
}