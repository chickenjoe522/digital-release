import json
import urllib.request
import urllib.parse
import urllib.error
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
        "year": YEAR
    })

    request = urllib.request.Request(
        API + "?" + params,
        headers={
            "User-Agent": "Mozilla/5.0 DigitalRelease/1.0",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("status") != "ok":
        raise RuntimeError(str(result))

    return result.get("data", {}).get("movies") or []


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main():
    ROOT.mkdir(parents=True, exist_ok=True)

    # Publish the manifest.
    manifest = json.loads(
        Path("manifest.json").read_text(encoding="utf-8")
    )
    save(ROOT / "manifest.json", manifest)

    movies = []
    seen = set()

    for page in range(1, 6):
        print("Fetching page", page)

        batch = fetch(page)

        if not batch:
            break

        for movie in batch:
            imdb = movie.get("imdb_code", "")

            if not imdb.startswith("tt") or imdb in seen:
                continue

            if int(movie.get("year") or 0) != YEAR:
                continue

            seen.add(imdb)
            movies.append(movie)

    metas = []

    for movie in movies:
        imdb = movie["imdb_code"]

        meta = {
            "id": imdb,
            "type": "movie",
            "name": movie.get("title") or "Unknown",
            "poster": movie.get("medium_cover_image"),
            "background": movie.get("large_cover_image"),
            "description": movie.get("description_full") or "",
            "releaseInfo": str(movie.get("year", "")),
            "imdbRating": str(movie.get("rating", "")),
            "genres": movie.get("genres") or []
        }

        # Only metadata is published.
        metas.append(meta)
        save(META / f"{imdb}.json", {"meta": meta})

    save(
        CATALOG / "digital_latest_2026.json",
        {"metas": metas}
    )

    print("Successfully generated", len(metas), "movies")


if __name__ == "__main__":
    main()
