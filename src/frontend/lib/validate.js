// Same rules as the backend (backend/onboarding/answers.py). The backend checks again;
// these are here so the user sees mistakes right away.

export const isEmail = (v) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v || "");
export const isPhone = (v) => /^[+()\-.\s\d]{7,20}$/.test(v || "");
export const isLinkedIn = (v) => /linkedin\.com\//i.test(v || "");
export const isWebsite = (v) => /^(https?:\/\/)?[^\s/]+\.[^\s]{2,}/i.test(v || "");
/** "2001-04-17" from a date input; must be a real date before today. */
export const isPastDate = (v) => {
  const d = new Date(`${v}T00:00:00`);
  return !Number.isNaN(d.getTime()) && d < new Date() && d.getFullYear() > 1900;
};

/** "Python, SQL; python" -> ["Python", "SQL"] */
export function splitList(text) {
  const seen = new Map();
  for (const part of (text || "").split(/[,;\n]/)) {
    const item = part.trim();
    if (item && !seen.has(item.toLowerCase())) seen.set(item.toLowerCase(), item);
  }
  return [...seen.values()];
}

export function validateDetails(r) {
  const errors = {};
  if (!r.first_name?.trim()) errors.first_name = "Add your first name.";
  if (!r.last_name?.trim()) errors.last_name = "Add your last name.";
  if (!isEmail(r.email)) errors.email = "Add a valid email address.";
  if (!isPhone(r.phone)) errors.phone = "Add a phone number, like +1 555 123 4567.";
  if (!r.location?.trim()) errors.location = "Add your city and state.";
  if (r.linkedin_url && !isLinkedIn(r.linkedin_url)) errors.linkedin_url = "This should be a linkedin.com link.";
  if (r.github_url && !/github\.com\//i.test(r.github_url)) errors.github_url = "This should be a github.com link.";
  if (r.portfolio_url && !isWebsite(r.portfolio_url)) errors.portfolio_url = "Enter a website address, like yourname.dev.";
  if (r.date_of_birth && !isPastDate(r.date_of_birth)) errors.date_of_birth = "Enter a date in the past.";
  if (r.postal_code && !/^[A-Za-z0-9][A-Za-z0-9 -]{1,9}$/.test(r.postal_code.trim())) {
    errors.postal_code = "Enter a postal code, like 07102.";
  }

  // Each job needs a title and company; each school needs a name. Errors are keyed "<entry _key>.<field>".
  for (const job of r.experience) {
    if (!job.title?.trim()) errors[`${job._key}.title`] = "Add the job title.";
    if (!job.company?.trim()) errors[`${job._key}.company`] = "Add the company.";
  }
  for (const ed of r.education) {
    if (!ed.school?.trim()) errors[`${ed._key}.school`] = "Add the school name.";
  }
  return errors;
}

export function validatePreferences(p) {
  const errors = {};
  if (p.target_roles.length === 0) errors.target_roles = "Pick or add at least one role.";
  if (p.min_salary !== null && (p.min_salary < 1000 || p.min_salary > 2_000_000)) {
    errors.min_salary = "Enter a yearly amount, like 85000.";
  }
  return errors;
}

export function validateEmployment(info) {
  const errors = {};
  for (const [key, value] of Object.entries(info)) {
    if (value === null) errors[key] = "Choose an answer.";
  }
  return errors;
}