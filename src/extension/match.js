// Picking the right option for an answer, in code. Shared by the content scripts (JA.pick).
// Order: exact (after normalizing, with synonyms and US state names) -> Yes/No prefix ->
// "No"-style answers -> whole-phrase contains -> word overlap with a clear winner.
// When nothing is clearly best, it returns no option plus the top candidates, so the agent can
// be asked (Phase 4) instead of guessing.
(() => {
  const JA = (globalThis.JA ??= {});

  const STATES = {
    al: "alabama", ak: "alaska", az: "arizona", ar: "arkansas", ca: "california", co: "colorado",
    ct: "connecticut", de: "delaware", fl: "florida", ga: "georgia", hi: "hawaii", id: "idaho",
    il: "illinois", in: "indiana", ia: "iowa", ks: "kansas", ky: "kentucky", la: "louisiana",
    me: "maine", md: "maryland", ma: "massachusetts", mi: "michigan", mn: "minnesota",
    ms: "mississippi", mo: "missouri", mt: "montana", ne: "nebraska", nv: "nevada",
    nh: "new hampshire", nj: "new jersey", nm: "new mexico", ny: "new york", nc: "north carolina",
    nd: "north dakota", oh: "ohio", ok: "oklahoma", or: "oregon", pa: "pennsylvania",
    ri: "rhode island", sc: "south carolina", sd: "south dakota", tn: "tennessee", tx: "texas",
    ut: "utah", vt: "vermont", va: "virginia", wa: "washington", wv: "west virginia",
    wi: "wisconsin", wy: "wyoming", dc: "district of columbia",
  };
  // Groups of answers that mean the same thing (compared after norm()).
  const SYNONYMS = [
    ["male", "man"], ["female", "woman"],
    ["united states", "us", "usa", "u s", "u s a", "united states of america", "america"],
    ["united kingdom", "uk", "u k", "great britain", "britain"],
    ["bachelor s degree", "bachelors", "bachelor", "b s", "bs", "b a", "ba", "bachelor of science", "bachelor of arts"],
    ["master s degree", "masters", "master", "m s", "ms", "m a", "ma", "master of science", "master of arts"],
  ];
  const DECLINE = /decline|wish to (answer|disclose|self)|want to answer|prefer not|not to (say|disclose|answer)/i;
  const NEGATIVE = /\b(no|not|never|none|don't|do not|haven't|have not)\b/i;
  const STOP = new Set(["the", "of", "and", "a", "an", "at", "in", "for", "to", "university", "college"]);

  const norm = (s) =>
    String(s ?? "")
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/&/g, " and ")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();

  /** "philadelphia pa" -> also "philadelphia pennsylvania" (and the other way round). Only the
   *  LAST word is treated as a state, so words like "in", "or", "me" elsewhere stay as they are. */
  const withStates = (n) => {
    const words = n.split(" ");
    const last = words.at(-1);
    const out = [n];
    if (words.length > 1 && STATES[last]) out.push([...words.slice(0, -1), STATES[last]].join(" "));
    for (const [abbr, name] of Object.entries(STATES)) {
      if (n.endsWith(` ${name}`)) out.push(`${n.slice(0, -name.length)}${abbr}`);
    }
    return out;
  };

  /** Every normalized way to write this answer. */
  const variants = (value) => {
    const out = new Set();
    for (const v of withStates(norm(value))) {
      out.add(v);
      for (const group of SYNONYMS) if (group.includes(v)) group.forEach((g) => out.add(g));
    }
    out.delete("");
    return out;
  };

  const stem = (w) => (w.length > 4 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w);
  const tokens = (n) => new Set(n.split(" ").filter((w) => w && !STOP.has(w)).map(stem));
  const overlap = (a, b) => {
    const A = tokens(a), B = tokens(b);
    if (!A.size || !B.size) return 0;
    let both = 0;
    for (const w of A) if (B.has(w)) both += 1;
    return both / (A.size + B.size - both); // Jaccard
  };

  /**
   * Best option for an answer.
   * -> {option, how} when one option is clearly right, else {option: null, candidates: [...]}.
   * allowDecline: pick "I don't wish to answer"-style options only if the answer itself says so.
   */
  JA.pick = (value, options) => {
    const opts = options
      .map((text, i) => ({ text: String(text), i, n: norm(text) }))
      .filter((o) => o.n);
    if (!opts.length || value == null || value === "") return { option: null, candidates: [] };
    const answer = norm(value);
    const wantsDecline = DECLINE.test(String(value));
    const pool = opts.filter((o) => wantsDecline || !DECLINE.test(o.text));
    const vs = variants(value);
    const one = (hits, how) => (hits.length === 1 ? { option: hits[0].text, how } : null);

    const exact = opts.filter((o) => vs.has(o.n) || withStates(o.n).some((x) => vs.has(x)));
    const found =
      one(exact, "exact") ??
      (["yes", "no"].includes(answer) ? one(pool.filter((o) => o.n.split(" ")[0] === answer), "yes/no") : null) ??
      (["no", "none"].includes(answer) ? one(pool.filter((o) => NEGATIVE.test(o.text)), "negative") : null) ??
      (answer.length > 3
        ? one(pool.filter((o) => [...vs].some((v) => ` ${o.n} `.includes(` ${v} `) || ` ${v} `.includes(` ${o.n} `))),
              "contains")
        : null);
    if (found) return found;

    const scored = pool
      .map((o) => ({ ...o, score: Math.max(...[...vs].map((v) => overlap(v, o.n))) }))
      .sort((a, b) => b.score - a.score);
    const [best, second] = scored;
    if (best && best.score >= 0.5 && best.score - (second?.score ?? 0) >= 0.15) return { option: best.text, how: "similar" };
    return { option: null, candidates: scored.filter((o) => o.score > 0).slice(0, 8).map((o) => o.text) };
  };

  // ---------------------------------------------------------------- places (location pickers)
  // Options look like "Philadelphia, Pennsylvania, United States". Compare city, state and country
  // separately, so "New Philadelphia, Pennsylvania" or "Philadelphia, Mississippi" never win.
  const PREFIX = /^(city|town|township|borough|village|municipality) of /;
  const PROVINCES = {
    on: "ontario", bc: "british columbia", ab: "alberta", qc: "quebec", mb: "manitoba", sk: "saskatchewan",
    ns: "nova scotia", nb: "new brunswick", nl: "newfoundland and labrador", pe: "prince edward island",
  };
  const stateKey = (s) => { const n = norm(s); return STATES[n] ?? PROVINCES[n] ?? n; };   // "PA" -> "pennsylvania"
  const same = (a, b) => a === b || SYNONYMS.some((g) => g.includes(a) && g.includes(b));  // "usa" = "united states"
  const title = (s) => s.replace(/\b\w/g, (c) => c.toUpperCase());

  /** place = {city, state?, country?} -> {option, how: "place"} | {option: null, candidates} */
  JA.pickPlace = (place, options) => {
    const city = norm(place?.city);
    if (!city) return { option: null, candidates: [] };
    const state = place.state ? stateKey(place.state) : null;
    const country = place.country ? norm(place.country) : null;
    const fits = (part) => (state && stateKey(part) === state) || (country && same(part, country));

    const ranked = [];
    for (const text of options) {
      const [first = "", ...rest] = String(text).split(",").map(norm).filter(Boolean);
      if (first.replace(PREFIX, "") !== city) continue;                      // the city must be exact
      const hasState = !!state && rest.some((p) => stateKey(p) === state);
      if (rest.length >= 2) {
        if (state && !hasState) continue;                                     // another state
        if (country && !same(rest.at(-1), country)) continue;                 // another country
      } else if (rest.length === 1 && (state || country) && !fits(rest[0])) continue;
      ranked.push({ text: String(text), rank: (hasState ? 2 : 0) + (PREFIX.test(first) ? 0 : 1) });
    }
    ranked.sort((a, b) => b.rank - a.rank);
    const [best, second] = ranked;
    if (best && (!second || best.rank > second.rank)) return { option: best.text, how: "place" };
    const candidates = (ranked.length ? ranked.map((r) => r.text)
      : options.filter((o) => norm(o).includes(city))).slice(0, 8);
    return { option: null, candidates };
  };

  /** What to type into a location search: "Philadelphia, PA" finds nothing, these do. */
  JA.placeQueries = (place) => {
    const city = String(place?.city ?? "").trim();
    const state = place?.state ? title(stateKey(place.state)) : "";
    return [...new Set([state && `${city}, ${state}`, city].filter(Boolean))];
  };

  JA.norm = norm;
  JA.DECLINE = DECLINE;
})();