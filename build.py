
import json
import re
import time
import socket
import urllib.request
import urllib.parse
import urllib.error

from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# ==========================================
# DIGITAL RELEASE CONFIGURATION
# ==========================================

ADDON_NAME = "Digital Release"

SOURCE_URL = (
    "https://yts.pw/browse-movies/"
    "0/all/all/0/latest/2026/en"
)

BASE_URL = "https://yts.pw/"
YEAR = 2026

ROOT = Path("site")
CATALOG_DIR = ROOT / "catalog" / "movie"
META_DIR = ROOT / "meta" / "movie"

CATALOG_ID = "digital_latest_2026"

MAX_PAGES = 5
MAX_MOVIES = 100


# ==========================================
# HTTP REQUEST
# ==========================================

def get_html(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 "
                          "(compatible; DigitalRelease/1.0)",
            "Accept": "text/html,application/xhtml+xml"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode(
                "utf-8", errors="replace"
            )

    except Exception as error:
        raise RuntimeError(
            f"Unable to retrieve {url}: {error}"
        ) from error


# ==========================================
# MOVIE LISTING HTML PARSER
# ==========================================

class MovieParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.movies = []
        self.card = None
        self.card_depth = 0
        self.depth = 0
        self.capture = None
        self.void_tags = {
            "area", "base", "br", "col", "embed",
            "hr", "img", "input", "link", "meta",
            "param", "source", "track", "wbr"
        }

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()

        if self.card is None:
            if (
                "browse-movie-wrap" in classes
                or "browse-movie-bottom" in classes
            ):
                self.card = {
                    "title": "",
                    "url": "",
                    "year": "",
                    "poster": ""
                }
                self.card_depth = self.depth

        if self.card is not None:

            if (
                tag == "a"
                and "browse-movie-title" in classes
            ):
                self.card["url"] = attrs.get("href", "")
                self.capture = "title"

            elif "browse-movie-year" in classes:
                self.capture = "year"

            elif tag == "img" and not self.card["poster"]:
                self.card["poster"] = (
                    attrs.get("data-src")
                    or attrs.get("data-lazy-src")
                    or attrs.get("src")
                    or ""
                )

        if tag not in self.void_tags:
            self.depth += 1

    def handle_data(self, data):
        if self.card is None or self.capture is None:
            return

        if self.capture in ("title", "year"):
            self.card[self.capture] += data.strip()

    def handle_endtag(self, tag):

        if self.card is not None and self.depth == self.card_depth + 1:
            if tag in ("a", "div"):
                pass

        if tag not in self.void_tags:
            self.depth = max(0, self.depth - 1)

        if (
            self.card is not None
            and self.depth == self.card_depth
            and tag == "div"
        ):
            self.finish_card()

        if tag == "a" and self.capture == "title":
            self.capture = None

    def finish_card(self):
        if self.card and self.card["title"] and self.card["url"]:
            self.movies.append(self.card)

        self.card = None
        self.capture = None


# ==========================================
# MOVIE DETAIL PARSER
# ==========================================

class DetailParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.metadata = {}
        self.imdb_id = ""
        self.genres = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "meta":
            key = (
                attrs.get("property")
                or attrs.get("name")
                or ""
            )

            value = attrs.get("content", "")

            if key and value:
                self.metadata[key.lower()] = value

        if tag == "a":
            href = attrs.get("href", "")

            match = re.search(
                r"imdb\.com/title/(tt\d+)",
                href
            )

            if match:
                self.imdb_id = match.group(1)


# ==========================================
# FETCH MOVIE LISTINGS
# ==========================================

def fetch_listings():

    all_movies = []
    seen_urls = set()

    for page in range(1, MAX_PAGES + 1):

        if page == 1:
            url = SOURCE_URL
        else:
            separator = "&" if "?" in SOURCE_URL else "?"
            url = SOURCE_URL + separator + f"page={page}"

        print(f"Fetching movie listing page {page}...")

        html = get_html(url)

        parser = MovieParser()
        parser.feed(html)

        if not parser.movies:
            print("No more movie cards detected.")
            break

        for movie in parser.movies:

            movie_url = urljoin(BASE_URL, movie["url"])

            if movie_url in seen_urls:
                continue

            seen_urls.add(movie_url)

            movie["url"] = movie_url

            if movie["year"]:
                if movie["year"].strip() != str(YEAR):
                    continue

            all_movies.append(movie)

            if len(all_movies) >= MAX_MOVIES:
                break

        if len(all_movies) >= MAX_MOVIES:
            break

        time.sleep(1)

    return all_movies


# ==========================================
# FETCH INDIVIDUAL MOVIE METADATA
# ==========================================

def fetch_details(movie):

    html = get_html(movie["url"])

    parser = DetailParser()
    parser.feed(html)

    metadata = parser.metadata

    imdb_id = parser.imdb_id

    if not imdb_id:
        # Do not invent IMDb identifiers.
        print("Skipping movie without IMDb ID:", movie["title"])
        return None

    title = (
        metadata.get("og:title")
        or movie["title"]
    )

    title = re.sub(
        r"\s*[-|]\s*YTS.*$",
        "",
        title,
        flags=re.IGNORECASE
    ).strip()

    description = (
        metadata.get("og:description")
        or metadata.get("description")
        or ""
    )

    poster = (
        metadata.get("og:image")
        or movie.get("poster")
        or ""
    )

    image = urljoin(movie["url"], poster) if poster else ""

    rating = (
        metadata.get("imdb:rating")
        or metadata.get("rating")
        or ""
    )

    release_info = (
        metadata.get("article:published_time")
        or movie.get("year")
        or str(YEAR)
    )

    result = {
        "id": imdb_id,
        "type": "movie",
        "name": title,
        "description": description,
        "releaseInfo": str(release_info)[:10],
        "poster": image
    }

    if rating:
        result["imdbRating"] = str(rating)

    return result


# ==========================================
# WRITE JSON FILES
# ==========================================

def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ==========================================
# MAIN BUILD
# ==========================================

def main():

    print("=" * 45)
    print("BUILDING", ADDON_NAME)
    print("=" * 45)

    # Publish manifest.
    manifest_path = Path("manifest.json")

    if not manifest_path.exists():
        raise FileNotFoundError(
            "manifest.json is missing from repository root"
        )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    # Keep the addon title exactly Digital Release.
    manifest["name"] = ADDON_NAME

    save_json(
        ROOT / "manifest.json",
        manifest
    )

    # Fetch movie listing.
    movies = fetch_listings()

    print("Movie listings found:", len(movies))

    if not movies:
        raise RuntimeError(
            "No movie listings found. "
            "Check YTS website availability or HTML structure."
        )

    metas = []
    seen_ids = set()

    for index, movie in enumerate(movies, 1):

        print(
            f"Processing {index}/{len(movies)}: "
            f"{movie['title']}"
        )

        try:
            meta = fetch_details(movie)

            if not meta:
                continue

            if meta["id"] in seen_ids:
                continue

            seen_ids.add(meta["id"])
            metas.append(meta)

            save_json(
                META_DIR / f"{meta['id']}.json",
                {"meta": meta}
            )

        except Exception as error:
            print(
                "Movie metadata error:",
                movie["title"],
                str(error)
            )

        time.sleep(0.5)

    if not metas:
        raise RuntimeError(
            "No valid IMDb metadata was generated."
        )

    # Exactly ONE catalog.
    save_json(
        CATALOG_DIR / f"{CATALOG_ID}.json",
        {"metas": metas}
    )

    print("=" * 45)
    print("BUILD SUCCESSFUL")
    print("Addon:", ADDON_NAME)
    print("Catalogs: 1")
    print("Movies:", len(metas))
    print("Metadata only: YES")
    print("Streams: NONE")
    print("=" * 45)


if __name__ == "__main__":
    main()
