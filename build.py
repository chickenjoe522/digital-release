
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
        "year": YEAR
    })

    request = urllib.request.Request(
        API + "?" + params,
        headers={"User-Agent": "DigitalRelease/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("status") != "ok":
        raise RuntimeError("YTS API returned an unsuccessful response")

    return data.get("data", {}).get("movies") or []


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main():
    manifest = json.loads(
        Path("manifest.json").read_text(encoding="utf-8")
    )

    save(ROOT / "manifest.json", manifest)

    movies = []
    seen = set()

    for page in range(1, 6):
        print("Fetching page:", page)

        for movie in fetch(page):
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

    print("SUCCESS:", len(metas), "movies generated")


if __name__ == "__main__":
    main()
