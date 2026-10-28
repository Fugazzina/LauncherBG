"""Generate personalized wallpaper recommendations using MDBList watch history and Gemini."""
import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

CACHE = Path("recommendations.json")
PREFERENCES = Path("preferences.json")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def api_json(url, *, headers=None, params=None):
    r = requests.get(url, headers=headers, params=params, timeout=35)
    r.raise_for_status()
    return r.json()


def get_history():
    key = os.environ["MDBLIST_API_KEY"]
    response = api_json("https://api.mdblist.com/sync/watched", params={"apikey": key})
    if not isinstance(response, dict):
        raise ValueError("Formato MDBList inatteso: atteso oggetto movies/shows")
    watched, history = set(), []
    for section, kind in (("movies", "movie"), ("shows", "show")):
        entries = response.get(section, [])
        if not isinstance(entries, list):
            raise ValueError(f"MDBList: {section} non è una lista")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            media = entry.get(kind) or entry
            if not isinstance(media, dict):
                continue
            ids = media.get("ids") or {}
            try:
                tmdb_id = int(ids.get("tmdb") or media.get("tmdb_id"))
            except (TypeError, ValueError):
                continue
            watched.add((kind, tmdb_id))
            history.append({
                "title": media.get("title") or media.get("name", ""),
                "year": media.get("year"), "type": kind,
                "last_watched": entry.get("last_watched_at"),
            })
    if not watched:
        raise ValueError("Nessun TMDB ID nella Watch History MDBList; controllare la risposta dell'API")
    history.sort(key=lambda x: x["last_watched"] or "", reverse=True)
    return watched, history[:400]


def ask_gemini(history):
    preferences = json.loads(PREFERENCES.read_text(encoding="utf-8"))
    prompt = (
        "Sei un esperto di consigli cinematografici. Proponi 65 film e serie TV reali, "
        "con un equilibrio tra titoli conosciuti e scoperte e includendo anime. "
        "Le preferenze esplicite pesano più della watch history: visto non significa apprezzato. "
        "Non riproporre i preferiti indicati e non proporre titoli presenti nella cronologia. "
        "Evita commedie romantiche, documentari, musical, biopic e opere deliberatamente lente. "
        "Rispondi con titolo originale/internazionale, anno di prima uscita e tipo (movie/show).\n"
        "Preferenze: " + json.dumps(preferences, ensure_ascii=False) + "\n"
        "Cronologia: " + json.dumps(history, ensure_ascii=False)
    )
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"type": "object",
            "properties": {"title": {"type": "string"}, "year": {"type": "integer"},
                           "type": {"type": "string", "enum": ["movie", "show"]}},
            "required": ["title", "year", "type"]}}}},
        "required": ["items"],
    }
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json",
                                   "responseSchema": schema, "temperature": 0.8}},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])["items"]


def resolve_titles(suggestions, watched):
    headers = {"Authorization": "Bearer " + os.environ["TMDB_BEARER_TOKEN"],
               "accept": "application/json"}
    chosen, unique = [], set()
    for candidate in suggestions:
        kind = candidate.get("type")
        title = str(candidate.get("title", "")).strip()
        if kind not in ("movie", "show") or not title:
            continue
        target = "movie" if kind == "movie" else "tv"
        try:
            data = api_json(f"https://api.themoviedb.org/3/search/{target}",
                            headers=headers, params={"query": title, "language": "en-US"})
        except requests.RequestException as exc:
            print(f"TMDB search error for {title}: {exc}")
            continue
        year = str(candidate.get("year", ""))
        name_key = "title" if kind == "movie" else "name"
        date_key = "release_date" if kind == "movie" else "first_air_date"
        matches = []
        for item in data.get("results", []):
            name = (item.get(name_key) or "").casefold()
            exact = name == title.casefold()
            same_year = (item.get(date_key) or "")[:4] == year
            if exact or (same_year and title.casefold() in name):
                matches.append((int(exact), int(same_year), item))
        if not matches:
            continue
        match = sorted(matches, key=lambda m: (m[0], m[1]), reverse=True)[0][2]
        identity = (kind, int(match["id"]))
        if identity in watched or identity in unique or not match.get("backdrop_path"):
            continue
        unique.add(identity)
        chosen.append({"tmdb_id": identity[1], "type": kind,
                       "title": match.get(name_key) or title})
        if len(chosen) >= 50:
            break
    return chosen


def get_personalized_items():
    watched, history = get_history()
    cache = None
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    try:
        updated = datetime.fromisoformat(cache["updated_at"]) if cache else None
    except (KeyError, TypeError, ValueError):
        updated = None
    is_expired = (updated is None or
                  datetime.now(timezone.utc) - updated > timedelta(days=7))
    if is_expired:
        try:
            items = resolve_titles(ask_gemini(history), watched)
            if len(items) < 10:
                raise ValueError(f"Solo {len(items)} raccomandazioni valide")
            cache = {"updated_at": datetime.now(timezone.utc).isoformat(), "items": items}
            CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            if not cache:
                raise
            print(f"Gemini non disponibile; uso cache: {exc}")
    items = [x for x in cache["items"]
             if (x["type"], int(x["tmdb_id"])) not in watched]
    if not items:
        raise ValueError("Nessuna raccomandazione disponibile: sfondi esistenti preservati")
    random.shuffle(items)
    return items[:20]
