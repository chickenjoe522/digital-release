import json
import urllib.request
import urllib.parse
from pathlib import Path

YEAR = 2026
API = "https://yts.mx/api/v2/list_movies.json"

ROOT = Path("site")
CATALOG = ROOT / "catalog/movie"
META = ROOT / "meta/movie"

def fetch(page):
    params = urllib.parse.urlencode({
        "limit": 50,
        "page": page,
        "sort_by": "date_added",
        "order_by": "desc",
        "with_rt_ratings": "true",
        "year": YEAR
    })

    request = urllib.request.Request(
        API + "?" + params,
        headers={"User-Agent": "DigitalRelease/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["data"].get("movies") or []

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def main():
    movies = []
    seen = set()

    for page in range(1, 6):
        batch = fetch(page)
        if not batch:
            break

        for movie in batch:
            imdb = movie.get("imdb_code", "")
            if imdb.startswith("tt") and imdb not in seen:
                seen.add(imdb)
                movies.append(movie)

    metas = []

    for movie in movies:
        imdb = movie["imdb_code"]

        meta = {
            "id": imdb,
            "type": "movie",
            "name": movie.get("title", ""),
            "poster": movie.get("medium_cover_image"),
            "background": movie.get("large_cover_image"),
            "description": movie.get("description_full") or "",
            "releaseInfo": str(movie.get("year", "")),
            "imdbRating": str(movie.get("rating", "")),
            "genres": movie.get("genres") or []
        }

        metas.append(meta)
        save(META / f"{imdb}.json", {"meta": meta})

    save(
        CATALOG / "digital_latest_2026.json",
        {"metas": metas}
    )

    print("Digital Release:", len(metas), "movies generated")

if __name__ == "__main__":
    main()
