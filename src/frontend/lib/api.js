// All calls to the Python backend go through here.
// Paths like "/api/profile" go to this site, and next.config.mjs forwards them to the backend.

export async function apiFetch(path, { method = "GET", body, headers, ...rest } = {}) {
  const isForm = body instanceof FormData;

  const res = await fetch(path, {
    method,
    credentials: "include", // send the login session cookie
    headers: isForm ? headers : { "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    ...rest,
  });

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      message = data.detail || data.message || message;
    } catch {
      // response wasn't JSON; keep the default message
    }
    throw new Error(message);
  }

  return res.status === 204 ? null : res.json();
}