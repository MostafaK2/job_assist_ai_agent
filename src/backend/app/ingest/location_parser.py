"""Greenhouse location text -> {"work_types": [...], "locations": [{city, state, country, region}]}.
All place data comes from geonamescache; typos via rapidfuzz. No place names in this file."""
import re
from functools import lru_cache

import geonamescache
from rapidfuzz import fuzz, process

WORK = {"remote": r"remote|distributed|anywhere|wfh", "hybrid": r"hybrid",
        "onsite": r"in[- ]?office|on[- ]?site|in[- ]person"}
WORK_RE = {w: re.compile(rf"\b(?:{p})\b", re.I) for w, p in WORK.items()}
NONE = ([], None, None, None)


def _k(s): return re.sub(r"\s+", " ", s.replace(".", "")).strip(" -").lower()


@lru_cache(1)
def _geo():
    gc, G = geonamescache.GeonamesCache(), {"countries": {}, "states": {}, "cities": {}, "region": {}}
    names = {k: v["name"] for k, v in gc.get_continents().items()}
    G["continents"] = {_k(n): n for n in names.values()}
    for c in gc.get_countries().values():
        G["region"][c["iso"]] = names[c["continentcode"]]
        name = c["name"].removeprefix("The ")
        for n in (name, c["iso"], c["iso3"], "".join(w[0] for w in name.split()) if " " in name else ""):
            if n:
                G["countries"].setdefault(_k(n), c["iso"])
    for s in gc.get_us_states().values():
        G["states"][_k(s["name"])] = G["states"][_k(s["code"])] = s["code"]
    for v in gc.get_cities().values():
        city = (v["name"], v["countrycode"], v["admin1code"], v["population"])
        for n in {v["name"], *(v["alternatenames"] if city[3] >= 100_000 else [])}:  # small towns' aliases are noise
            G["cities"].setdefault(_k(n), []).append(city)
    G["big"] = sorted({c[0] for cs in G["cities"].values() for c in cs if c[3] >= 100_000})
    return G


def _lookup(raw):
    G, k = _geo(), _k(raw)
    if len(k) < 2 or (len(k) <= 3 and not raw.strip(" .-").isupper()):  # "IN" = India, "in" = a word
        return NONE
    st, co, cities = G["states"].get(k), G["countries"].get(k), G["cities"].get(k, [])
    if len(k) <= 3:
        cities = [c for c in cities if c[3] >= 500_000]                 # "SEA", "CHI" yes; "TOR" no
    if st or co:  # a city only wins when clear: "New York", "Washington", "SF", "LA"
        cities = [c for c in cities if (st and c[1] == "US" and c[2] == st)
                  or (c[3] >= 500_000 and (_k(c[0]) == k or len(k) <= 3))]
    return cities, st, co, G["continents"].get(k)


def _find(raw):
    """Whole text, hyphens as spaces, then the longest capitalised word run ("Dallas Warehouse")."""
    for text in (raw, raw.replace("-", " ")):
        if any(hit := _lookup(text)):
            return hit
    words = raw.replace("-", " ").split()
    for n in range(len(words) - 1, 0, -1):
        for i in range(len(words) - n + 1):
            if words[i][:1].isupper() and any(hit := _lookup(" ".join(words[i:i + n]))):
                return hit
    return NONE


def _fit(cands, st, co):
    return [c for c in cands if (st and c[1] == "US" and c[2] == st) or (co and c[1] == co)]


def _fuzzy(raw, area):
    G = _geo()
    pool = sorted({c[0] for cs in G["cities"].values() for c in _fit(cs, *area)}) if area else G["big"]
    hit = process.extractOne(raw, pool, scorer=fuzz.ratio, score_cutoff=85 if area else 90)
    return (_fit(G["cities"][_k(hit[0])], *area) if area else G["cities"][_k(hit[0])]) if hit else []


def _segment(seg):
    seg = re.sub(r"\b([A-Z]{2,3})-\s*", r"\1, ", seg)                # "US-SF", "CA-Toronto"
    toks, found = [], []
    for t in re.split(r"\s*(?:,|\s-\s|:)\s*", seg):
        work = any(rx.search(t) for rx in WORK_RE.values())
        for rx in WORK_RE.values():
            t = rx.sub(" ", t)
        if t.strip(" -"):
            cities, st, co, cont = _find(t.strip(" -"))
            cities = [c for c in cities if c[3] >= 100_000] if work else cities  # not "Opportunity, WA"
            toks.append((t.strip(" -"), work))
            found.append((cities, st, co, cont))
    places, lead, province = [], None, None
    us = lambda: any(c[1] == "US" for p in places for c in p.get("_c", [])) or (lead and lead[1] == "US")
    for i, ((raw, work), (cities, st, co, cont)) in enumerate(zip(toks, found)):
        nxt = found[i + 1] if i + 1 < len(found) else NONE
        cur = places[-1] if places and "_c" in places[-1] else None
        if cur and (st or co) and (hit := _fit(cur["_c"], st, None) or _fit(cur["_c"], None, co)):
            cur["_c"] = hit                                           # "Seattle, WA", "Toronto, CA"
            continue
        if cur and st and not cities and cur["_i"] == i - 1:          # "Fairfield, NJ": smaller namesake
            cur["_c"] = [(toks[i - 1][0], "US", st, 0)]
            continue
        if not (cities or st or co or cont):                          # typo, small town or province
            if work:
                continue
            area = next(((f[1], f[2]) for f in found[i + 1:i + 3] if f[1] or f[2]), lead)
            cities = _fuzzy(raw, area) or ([(raw, "US" if area[0] else area[1], area[0] or "", 0)]
                                           if area and not cur else [])
            if not cities:
                if cur and not cur.get("state"):
                    cur["state"] = raw                                # "Munich, Bavaria, Germany"
                continue
        if cities and not (st or co) and nxt[2] and not nxt[1] and not _fit(cities, None, nxt[2]) \
                and all(c[3] < 500_000 for c in cities):              # "Toronto, Ontario, Canada"
            if cur and _fit(cur["_c"], None, nxt[2]):
                cur.setdefault("state", raw)
            else:
                province = raw                                        # "Remote - Ontario, Canada"
            continue
        if cities:
            places.append({"_c": (lead and _fit(cities, *lead)) or cities, "_i": i})  # "US-SF"
        elif cont and not (st or co):
            places.append({"_cont": cont})                            # "North America"
        elif not places and not lead:
            lead = (st, "US") if st and (not co or co == "US" or nxt[2] == "US") else (None, co)
        elif lead and not places:
            if co == lead[1] and not st or (st and st == lead[0]):
                continue                                              # "Texas, United States"
            if st and not lead[0] and lead[1] == "US":
                lead = (st, "US")                                     # "US, Georgia"
            else:
                places.append({"state": lead[0], "country": lead[1]})
                lead = (st, "US") if st and not co else (None, co)
        else:
            is_state = st and (not co or co == "US" or us())          # "US-Georgia" is the state
            places.append({"state": st if is_state else province, "country": "US" if is_state else co})
    if lead and not any("_c" in p for p in places):
        places.insert(0, {"state": lead[0] if lead[1] == "US" else province, "country": lead[1]})
    return places


def parse_location(text: str | None) -> dict:
    text = (text or "").replace("D.C", "DC")
    bare = re.sub(r"\([^)]*\)?", " ", text)                          # "(3 days/week in office)"
    work = sorted(w for w, rx in WORK_RE.items() if rx.search(bare)) or \
        sorted(w for w, rx in WORK_RE.items() if rx.search(text))
    out, G = [], _geo()
    for seg in re.split(r"\s*(?:;|\||/|&|•|\bor\b|\band\b)\s*", bare, flags=re.I):
        for p in _segment(seg):
            if "_c" in p:
                name, co, st, _ = max(p["_c"], key=lambda c: c[3])
                p.update(city=name, country=co, state=st if co == "US" else p.get("state"))
            loc = {k: p.get(k) for k in ("city", "state", "country")}
            loc["region"] = G["region"].get(p.get("country")) or p.get("_cont")
            if (loc := {k: v for k, v in loc.items() if v}) and loc not in out:
                out.append(loc)
    return {"work_types": work, "locations": out}


def parse_job_location(job: dict, description_text: str | None = None) -> dict:
    """For the sync: the location string, then the job's offices for places,
    then the description for work type (only when the location didn't say)."""
    r = parse_location((job.get("location") or {}).get("name"))
    if not r["locations"]:
        for office in job.get("offices") or []:
            o = parse_location(office.get("location") or office.get("name"))
            r["locations"] += [l for l in o["locations"] if l not in r["locations"]]
            r["work_types"] = sorted({*r["work_types"], *o["work_types"]})
    if not r["work_types"]:
        r["work_types"] = work_types_from_description(description_text)
    return r

## --------------

DESC_WORK = {  # phrases that describe THIS job, not company perks
    "remote": r"(?:fully|100%|completely) remote|remote[- ](?:first|role|position|opportunity|job|work)|"
              r"work(?:ing)? remotely|(?:role|position|job) is remote|remote (?:within|from|in) (?:the )?[A-Z]",
    "hybrid": r"hybrid|(?:\d|one|two|three|four|five) days? (?:a|per|each) week (?:in|at) (?:the|our|an) office|"
              r"in[- ]office (?:\d|one|two|three|four)",
    "onsite": r"on[- ]?site|in[- ]office|in[- ]person|office[- ]based",
}
DESC_RE = {w: re.compile(rf"\b(?:{p})\b", re.I) for w, p in DESC_WORK.items()}
NOT_JOB = re.compile(r"interview|benefit|perk|stipend|equal opportunity|accommodat", re.I)

def work_types_from_description(text: str | None) -> list[str]:
    """Remote / hybrid / onsite from sentences about the job (skips interview, perks, EEO text)."""
    found = set()
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text or ""):
        if NOT_JOB.search(sentence):
            continue
        hits = {w for w, rx in DESC_RE.items() if rx.search(sentence)}
        found |= {"onsite"} if re.search(r"\bnot (?:a |fully )?remote\b", sentence, re.I) else hits
    if "hybrid" in found:
        found.discard("onsite")                      # "hybrid: 3 days in office" is not on-site
    return sorted(found)