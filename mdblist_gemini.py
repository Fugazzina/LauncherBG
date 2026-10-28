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
    """Read EVERY cursor-paginated MDBList page, deduplicating films and shows.

    Episode/season records are only attributed to a show if they contain
    the show's own TMDB ID. An episode's ID must never become a show ID.
    """
    key = os.environ["MDBLIST_API_KEY"]
    url = "https://api.mdblist.com/sync/watched"
    cursor = None
    seen_cursors = set()
    watched = set()
    latest = {}
    counts = {"movies": 0, "shows": 0, "seasons": 0, "episodes": 0}
    missing_tmdb = 0

    for page_no in range(1, 201):
        params = {"apikey": key, "limit": 500}
        if cursor:
            params["cursor"] = cursor

        response = api_json(url, params=params)
        if not isinstance(response, dict):
            raise ValueError("MDBList: risposta /sync/watched non valida")

        page_counts = {}
        for section, kind in (
            ("movies", "movie"), ("shows", "show"),
            ("seasons", "show"), ("episodes", "show")
        ):
            entries = response.get(section) or []
            if not isinstance(entries, list):
                raise ValueError(f"MDBList: campo {section} non valido")

            counts[section] += len(entries)
            page_counts[section] = len(entries)

            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                if section == "movies":
                    media = entry.get("movie") or entry
                elif section == "shows":
                    media = entry.get("show") or entry
                else:
                    # Season/episode entries might carry a parent show.
                    media = entry.get("show")
                    if not isinstance(media, dict):
                        nested = entry.get("season" if section == "seasons" else "episode")
                        media = nested.get("show") if isinstance(nested, dict) else None

                if not isinstance(media, dict):
                    continue
                ids = media.get("ids") or {}
                try:
                    tmdb_id = int(ids.get("tmdb") or media.get("tmdb_id"))
                except (TypeError, ValueError, AttributeError):
                    missing_tmdb += 1
                    continue

                identity = (kind, tmdb_id)
                watched.add(identity)
                watched_at = entry.get("last_watched_at") or entry.get("watched_at") or ""
                description = {
                    "title": media.get("title") or media.get("name") or "",
                    "year": media.get("year"), "type": kind,
                    "last_watched": watched_at,
                }
                if identity not in latest or watched_at > (latest[identity]["last_watched"] or ""):
                    latest[identity] = description

        pagination = response.get("pagination") or {}
        if not isinstance(pagination, dict):
            raise ValueError("MDBList: paginazione non valida")
        has_more = pagination.get("has_more", False)
        next_cursor = pagination.get("next_cursor")
        print(
            f"[MDBList] Pagina {page_no}: "
            + ", ".join(f"{key}={value}" for key, value in page_counts.items())
            + f"; titoli unici={len(watched)}; altre pagine={bool(has_more)}"
        )

        if not has_more:
            break
        if not next_cursor or not isinstance(next_cursor, str):
            raise ValueError("MDBList indica altre pagine ma non fornisce next_cursor")
        if next_cursor == cursor or next_cursor in seen_cursors:
            raise ValueError("MDBList ha restituito un cursore ripetuto: sincronizzazione interrotta")
        if not any(page_counts.values()):
            raise ValueError("MDBList ha restituito una pagina vuota con has_more=True")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    else:
        raise ValueError("MDBList: superato il limite di 200 pagine, sincronizzazione incompleta")

    print(
        f"[MDBList diagnostica] pagine={page_no}; "
        + ", ".join(f"{key}={value}" for key, value in counts.items())
        + f"; senza ID show/movie TMDB={missing_tmdb}; titoli unici={len(watched)}"
    )
    if not watched:
        raise ValueError("Nessun titolo valido letto dalla Watch History MDBList")

    history = sorted(
        latest.values(), key=lambda item: item["last_watched"] or "", reverse=True
    )
    return watched, history[:400]


def ask_gemini(history):
    preferences = json.loads(PREFERENCES.read_text(encoding="utf-8"))
    prompt = (
        "Sei un esperto di consigli cinematografici. Proponi 65 titoli reali: "
        "35 film e 30 serie TV (anime compresi), distribuiti tra i generi preferiti. "
        "Mantieni un equilibrio tra titoli conosciuti e scoperte. "
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
            "required": ["title", "year", "type"]}}},
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
    limits = {"movie": 30, "show": 20}
    selected_counts = {"movie": 0, "show": 0}
    for candidate in suggestions:
        kind = candidate.get("type")
        title = str(candidate.get("title", "")).strip()
        if kind not in ("movie", "show") or not title:
            continue
        if selected_counts[kind] >= limits[kind]:
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
        selected_counts[kind] += 1
        chosen.append({"tmdb_id": identity[1], "type": kind,
                       "title": match.get(name_key) or title})
        if len(chosen) >= 50:
            break
    print(f"[Gemini] Titoli validati: {len(chosen)}; film={selected_counts['movie']}; serie={selected_counts['show']}")
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
    # Older recommendation caches were produced from only the first history page.
    is_expired = (updated is None or
                  datetime.now(timezone.utc) - updated > timedelta(days=7)
                  or (cache or {}).get("history_version") != 3)
    if is_expired:
        try:
            items = resolve_titles(ask_gemini(history), watched)
            if len(items) < 10:
                raise ValueError(f"Solo {len(items)} raccomandazioni valide")
            cache = {"updated_at": datetime.now(timezone.utc).isoformat(), "history_version": 3, "items": items}
            CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            if not cache:
                raise
            print(f"Gemini non disponibile; uso cache: {exc}")
    excluded = [x for x in cache["items"]
                if (x["type"], int(x["tmdb_id"])) in watched]
    items = [x for x in cache["items"]
             if (x["type"], int(x["tmdb_id"])) not in watched]
    print(f"[MDBList diagnostica] raccomandazioni in cache: {len(cache['items'])}; "
          f"escluse perche viste: {len(excluded)}; rimanenti: {len(items)}")
    if not items:
        raise ValueError("Nessuna raccomandazione disponibile: sfondi esistenti preservati")
    random.shuffle(items)
    return items[:20]
