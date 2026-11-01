"""Filimo and Namava catalog tools: search, title details, episodes, new releases, front-page picks, genre browse."""

from __future__ import annotations

import asyncio
import html
import re
from typing import Annotated, Any, Literal
from urllib.parse import quote

from pydantic import Field

from .http import FILIMO, NAMAVA, ApiError, fetch
from .registry import tool

FILIMO_SITE = "https://www.filimo.com"
NAMAVA_SITE = "https://www.namava.ir"
NAMAVA_IMG = "https://static.namava.ir"

Site = Literal["both", "filimo", "namava"]
Kind = Literal["all", "movie", "series"]
Limit = Annotated[int, Field(description="How many titles to return.", ge=1, le=40)]
Ref = Annotated[
    str,
    Field(
        description="Title ref from vod_search, vod_new, vod_browse or vod_featured, e.g. 'filimo:0bd4p', 'filimo:150570' or 'namava:series:2377'.",
        pattern=r"^(filimo:[A-Za-z0-9]{3,12}|namava:(movie|series):\d{1,9})$",
    ),
]

# Filimo genre tag ids (read from /movie/movie/filter/tagid/1) and Namava category-group slugs (read from title details).
FILIMO_GENRES = {
    "اکشن": 1000056, "کمدی": 1000060, "وحشت": 1000063, "انیمیشن": 1000051, "علمی تخیلی": 1000059,
    "تاک شو": 1000071, "عاشقانه": 1000061, "جنایی": 1000064, "درام": 1000053, "ماجراجویی": 1000057,
    "معمایی": 1000065, "ریلیتی شو": 1000075, "فانتزی": 1000058, "وسترن": 1000062, "هیجان انگیز": 1000066,
    "خانوادگی": 1000067, "جنگی": 1000055, "ورزشی": 1000068, "تاریخی": 1000054, "بیوگرافی": 1000052,
    "مذهبی": 1000074, "مستند": 1000070, "موزیکال": 1000069, "موسیقی": 1000072, "کوتاه": 1000073,
    "تئاتر": 1000080, "گیم شو": 1000078,
}  # fmt: skip
FILIMO_EN = {
    "action": "اکشن", "comedy": "کمدی", "horror": "وحشت", "animation": "انیمیشن", "sci-fi": "علمی تخیلی",
    "talk-show": "تاک شو", "romance": "عاشقانه", "crime": "جنایی", "drama": "درام", "adventure": "ماجراجویی",
    "mystery": "معمایی", "reality-tv": "ریلیتی شو", "fantasy": "فانتزی", "western": "وسترن",
    "thriller": "هیجان انگیز", "family": "خانوادگی", "war": "جنگی", "sport": "ورزشی", "history": "تاریخی",
    "biography": "بیوگرافی", "religious": "مذهبی", "documentary": "مستند", "musical": "موزیکال",
    "music": "موسیقی", "short": "کوتاه", "theater": "تئاتر", "game-show": "گیم شو",
}  # fmt: skip
NAMAVA_GENRES = {
    "درام": "drama", "جنایی": "crime", "اکشن": "action", "مهیج": "thriller", "برترین\u200cها": "tops",
    "کمدی": "comedy", "ورزشی": "sport", "فانتزی": "fantasy", "جنگی": "war", "انیمه و انیمیشن": "anime-animation",
    "خانوادگی": "family", "کودک": "kid", "مستند": "documentary", "تاریخی": "history", "عاشقانه": "romance",
    "علمی تخیلی": "scifi", "بیوگرافی": "biography", "اجتماعی": "social", "فیلم تئاتر": "film-theater",
    "موزیکال": "rhythmic", "ترسناک": "horror", "رازآلود": "mystery", "ماجراجویی": "adventure", "کلاسیک": "classic",
    "اسکار": "oscar", "کره ای": "korean", "ترکی": "turkish", "هندی": "indian", "ایرانی": "persian",
    "فیلم کوتاه": "short-movie", "ریلیتی شو": "reality show", "دوبله نماوا": "exclisuve-dubs",
    "آموزش و سرگرمی": "education", "وسترن": "western",
}  # fmt: skip
NAMAVA_ALIASES = {  # Filimo-style or English names that map onto a Namava group
    "کوتاه": "فیلم کوتاه", "short": "فیلم کوتاه", "reality-tv": "ریلیتی شو", "dubbed": "دوبله نماوا",
    "هیجان انگیز": "مهیج", "انیمیشن": "انیمه و انیمیشن", "انیمه": "انیمه و انیمیشن", "تئاتر": "فیلم تئاتر",
    "animation": "انیمه و انیمیشن", "anime": "انیمه و انیمیشن", "sci-fi": "علمی تخیلی", "scifi": "علمی تخیلی",
    "وحشت": "ترسناک", "معمایی": "رازآلود", "theater": "فیلم تئاتر", "musical": "موزیکال", "thriller": "مهیج", "kids": "کودک", "tops": "برترین\u200cها",
}  # fmt: skip
NAMAVA_EN = {v: k for k, v in NAMAVA_GENRES.items() if v.isascii() and " " not in v}
# Filimo curated lists (slugs from its site menu, "مجموعه\u200cها" and "کودک"); `<slug>/<other_data>` adds the site's own filter.
FILIMO_LISTS = {
    "imdbtop250": "250 فیلم برتر IMDB", "10678123": "برگزیدگان جشنواره ها", "irbestsell": "پرفروش های سینمای ایران",
    "Korean": "فیلم و سریال کره\u200cای", "turkishseries": "سریال ترکی", "IndianMovies": "فیلم هندی", "anime": "انیمه",
    "VisionImpaired": "مخصوص نابینایان", "HearImpaired": "مخصوص ناشنوایان", "comedyplus": "کمدی پلاس",
    "ExclusiveSeries": "سریال های اختصاصی", "EkraneOnline": "اکران آنلاین", "kids": "خانه کودک (چند ردیف)",
    "IranianKid": "کودک ایرانی", "SpongeBob": "باب اسفنجی", "pawpatrol": "سگ\u200c های نگهبان",
    "filimokidsadventure": "ماجراجویی کودک", "miraculous": "دختر کفشدوزکی",
    "filimokids_DubbedExclusively": "دوبله اختصاصی کودک", "HotelTransylvania": "هتل ترانسیلوانیا",
    "TheBossBaby": "بچه رئیس", "monsters": "اژدها و هیولاها", "cars": "ماشین\u200cها", "princess": "پرنسس",
    "animated_under_15": "تازه\u200cهای فیلیمو کودک (زیر 15 سال)", "animated_under_15/under_3": "کودک زیر 3 سال",
    "animated_under_15/under_6": "کودک زیر 6 سال", "animated_under_15/under_12": "کودک زیر 12 سال",
}  # fmt: skip
NAMAVA_SPECIAL = {  # Namava lists that are not category groups or post groups
    "popular": "پربازدیدترین ها", "latest_movies": "فیلم های جدید", "latest_series": "سریال های جدید",
    "coming_soon": "به زودی (تاریخ پخش نامشخص)", "trending": "پرجستجوترین ها",
}  # fmt: skip
NAMAVA_COMING_SOON = 1384  # post group behind the site's "به زودی" row
FILIMO_SORT = {
    "default": None, "newest_added": "news", "year_new": "new_nocomingsoon", "year_old": "old",
    "rating": "user_rate", "imdb": "imdb_rate",
}  # fmt: skip
COUNTRIES = {
    "iran", "america", "japan", "england", "s_korea", "turkey", "france", "india", "canada", "germany", "spain",
    "china", "italy", "foreign", "ctry_other",
}  # fmt: skip

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _en(s: Any) -> str:
    return str(s).translate(_DIGITS) if s is not None else ""


def _int(s: Any) -> int | None:
    m = re.search(r"\d+", _en(s))
    return int(m.group()) if m else None


def _num(s: Any) -> float | None:
    try:
        v = float(_en(s))
    except ValueError:
        return None
    return v or None  # 0 means "no value" on both sites


def _text(s: Any, limit: int = 500) -> str:
    """Plain text from the sites' HTML snippets, clipped."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    t = re.sub("[" + "".join(map(chr, (0x200B, 0x200E, 0x200F, 0xFEFF))) + "]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def _norm(s: str) -> str:
    """Matching key for titles: Arabic letters to Persian, no ZWNJ/spaces/punctuation, ASCII digits, lowercase."""
    s = _en(s).replace("ي", "ی").replace("ك", "ک").replace("\u200c", "")
    return re.sub(r"[\W_]+", "", s).lower()


def _parse_ref(ref: str) -> tuple[str, str, str]:
    """(site, kind, id). Filimo refs carry no kind: '' means look at the title."""
    parts = ref.split(":")
    return (parts[0], parts[1], parts[2]) if parts[0] == "namava" else ("filimo", "", parts[1])


# --- Filimo -----------------------------------------------------------------------------------------------------


def _f_url(parts: str) -> str:
    return f"{FILIMO}/movie/{parts}"


def _f_item(a: dict[str, Any]) -> dict[str, Any]:
    """One title from a Filimo list/search row. Series episodes collapse to their series."""
    serial = a.get("serial") or {}
    series = bool(serial.get("enable"))
    uid = str(serial.get("parent_id") or a.get("uid")) if series else str(a.get("uid"))
    genres = [g.get("title") for g in a.get("categories") or []] or [
        g for g in (a.get("cat_title_str") or "").split(",") if g
    ]
    badge = a.get("badge") or {}
    title = a.get("movie_title")
    if series and title and " - فصل" in title:  # person and list pages return episodes; show the series name
        title = serial.get("parent_title") or title.split(" - فصل")[0]
    return {
        "site": "filimo",
        "ref": f"filimo:{uid}",
        "title": title,
        "title_en": re.sub(r"\s+S\d+E\d+$", "", a.get("movie_title_en") or "") or None,  # drop the episode tag
        "kind": "series" if series else "movie",
        "year": _int(a.get("pro_year")),
        "rating": _num(a.get("rate_avrage")),
        "rating_pct": _int(a.get("avg_rate_label")),
        "imdb": _num(a.get("imdb_rate")),
        "genres": genres,
        "age": a.get("age_range"),
        "free": bool(badge.get("free")) or None,
        "exclusive": bool(badge.get("exclusive")) or None,
        "summary": _text(a.get("descr"), 220),
        "url": f"{FILIMO_SITE}/m/{uid}",
    }


def _f_rows(doc: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """(row title, items) for each movie row of a Filimo list document."""
    movies = {str(x["id"]): x["attributes"] for x in doc.get("included", []) if x["type"] == "movies"}
    rows = []
    for r in doc.get("data", []):
        ids = [m["id"] for m in r["relationships"].get("movies", {}).get("data", [])]
        if r["attributes"].get("output_type") == "movie" and ids:
            items, seen = [], set()
            for i in ids:
                if (a := movies.get(str(i))) and (it := _f_item(a))["ref"] not in seen:
                    seen.add(it["ref"])
                    items.append(it)
            rows.append((r["attributes"].get("link_text") or r["attributes"].get("title") or "", items))
    return rows


def _f_list(tag: Any, kind: str = "all", sort: str | None = None, country: str | None = None) -> str:
    """List URL. The site's filters live in one path segment: other_data/<movie|series|tag>-<sort>-<country>."""
    parts = [f"list/tagid/{tag}"]
    if sort or country:
        parts.append(f"other_data/{kind if kind != 'all' else 'tag'}-{sort or ''}-{country or ''}".rstrip("-"))
    elif kind != "all":
        parts.append(f"other_data/{kind}")
    return _f_url("movie/" + "/".join(parts))


async def _f_search(q: str, kind: str, limit: int) -> list[dict[str, Any]]:
    doc = await fetch(f"{FILIMO}/movie/movie/list/tagid/1000300/text/{quote(q, safe='')}")
    items = [i for _, row in _f_rows(doc) for i in row]
    return [i for i in items if kind in ("all", i["kind"])][:limit]


MAX_F_PAGES = 5  # loadmore requests per call (40 rows each)


async def _f_pages(
    tag: Any, kind: str, sort: str | None, country: str | None, page: int, limit: int, other: str | None = None
) -> list[dict[str, Any]] | None:
    """Titles number (page-1)*limit .. page*limit of a Filimo list, or None if the list has no paged main row.

    The site's "load more" endpoint pages the main list 40 rows at a time (series collapsed with show_serial_parent);
    the first list call holds only a part of it. The list's own link says which tag and filter to page (named lists
    such as imdbtop250 page a different tag and sort); lists without a link (filtered genres) use the filter segment
    `<country>-<sort>-<movie|series|tag>`, the reverse of the list URL. `other` is a raw list filter (kids age).
    Stops after MAX_F_PAGES requests.
    """
    doc = await fetch(
        _f_url(f"movie/list/tagid/{tag}/other_data/{other}") if other else _f_list(tag, kind, sort, country)
    )
    link = next(
        (
            r["attributes"]["links"]["self"]
            for r in doc.get("data", [])
            if r["attributes"].get("more_type") == "infinity" and (r["attributes"].get("links") or {}).get("self")
        ),
        None,
    )
    if link:
        base = re.sub(r"/page/\d+$", "", link).replace("/perpage/", "/show_serial_parent/1/perpage/", 1)
    else:
        seg = (
            f"/other_data/{country or ''}-{sort or ''}-{kind if kind != 'all' else 'tag'}"
            if sort or country or kind != "all"
            else ""
        )
        base = _f_url(f"movie/loadmore/tagid/{tag}/more_type/infinity/show_serial_parent/1{seg}/perpage/40")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for n in range(1, MAX_F_PAGES + 1):
        try:
            doc = await fetch(f"{base}/page/{n}")
        except ApiError as e:
            if n == 1 and e.status == 404:  # not a paged list (a home-style page of several rows)
                return None
            raise
        rows = [i for _, row in _f_rows(doc) for i in row]
        if not rows:
            if n == 1:
                return None
            break
        for i in rows:
            if i["ref"] not in seen:  # a page can repeat series seen on an earlier page
                seen.add(i["ref"])
                items.append(i)
        if len(items) >= page * limit:
            break
    return items[(page - 1) * limit : page * limit]


async def _f_related(id_: str) -> list[tuple[str, list[dict[str, Any]]]]:
    """Rows of Filimo's `related` endpoint (needs the numeric id): "بازی\u200cهای <actor>", "به\u200cنویسندگی <writer>", genre rows."""
    g = (await fetch(_f_url(f"movie/one/uid/{id_}")))["data"]["attributes"]["General"]
    serial = g.get("serial") or {}  # a series answers with its latest episode; its own id is the parent id
    num = serial.get("parent_id") if serial.get("enable") else g["id"]
    return _f_rows(await fetch(_f_url(f"movie/related/movieid/{num}")))


def _f_people(rows: list[tuple[str, list[dict[str, Any]]]]) -> dict[str, list[str]]:
    """Cast and writers named in the titles of related rows."""
    out: dict[str, list[str]] = {"cast": [], "writers": []}
    for t, _ in rows:
        if m := re.match(r"^بازی\u200cهای\s+(.+)$", t.strip()):
            out["cast"].append(m.group(1).strip())
        elif m := re.match(r"^به\u200cنویسندگی\s+(.+)$", t.strip()):
            out["writers"].append(m.group(1).strip())
    return out


async def _gather(jobs: dict[str, Any], out: dict[str, Any]) -> dict[str, Any]:
    """Run per-site coroutines together; a failing site goes to out["errors"], all failing raises."""
    res = await asyncio.gather(*jobs.values(), return_exceptions=True)
    errors = {}
    for name, r in zip(jobs, res, strict=True):
        if isinstance(r, ApiError):
            errors[name] = str(r)
        elif isinstance(r, BaseException):
            raise r
        else:
            out[name] = r
    if errors and len(errors) == len(jobs):
        raise ApiError("; ".join(errors.values()))
    if errors:
        out["errors"] = errors
    return out


# --- Namava -----------------------------------------------------------------------------------------------------


def _n_ref(kind: str, id_: Any) -> str:
    return f"namava:{'series' if str(kind).lower() == 'series' else 'movie'}:{id_}"


def _n_url(kind: str, id_: Any, title: Any) -> str:
    """Page URL. namava.ir answers 404 without a slug after the id; any slug works, the title is the normal one."""
    slug = re.sub(r"\s+", "_", str(title or "x").strip())
    return f"{NAMAVA_SITE}/{'series' if str(kind).lower() == 'series' else 'movie'}/{id_}-{slug}"


def _n_img(path: Any) -> str | None:
    return f"{NAMAVA_IMG}{path}" if isinstance(path, str) and path.startswith("/") else path or None


def _n_item(x: dict[str, Any]) -> dict[str, Any]:
    """One title from a Namava search or list row (these carry little more than id, type, name, year)."""
    kind = "series" if str(x.get("type")).lower() == "series" else "movie"
    id_ = x.get("id")
    return {
        "site": "namava",
        "ref": _n_ref(kind, id_),
        "title": x.get("name") or x.get("caption"),
        "kind": kind,
        "year": _int(x.get("startProductionYear")),
        "free": True if x.get("contentPlayAccessType") == "Free" else None,
        "upcoming": True if x.get("unknownDatePublish") else None,
        "url": _n_url(kind, id_, x.get("name") or x.get("caption")),
        "image": _n_img(x.get("imageUrl") or x.get("image_url")),
    }


async def _n_search(q: str, kind: str, limit: int) -> list[dict[str, Any]]:
    doc = await fetch(f"{NAMAVA}/v5.0/search/advance", {"type": "all", "count": 40, "page": 1, "query": q})
    groups = (((doc.get("result") or {}).get("result_items") or [{}])[0]).get("groups") or {}
    items = [_n_item(x) for x in (groups.get("Media") or {}).get("items") or []]
    return [i for i in items if kind in ("all", i["kind"])][:limit]


async def _n_detail(kind: str, id_: str) -> dict[str, Any]:
    doc = await fetch(f"{NAMAVA}/v2.0/medias/{id_}/single-{kind}")
    if not doc.get("succeeded") or not doc.get("result"):
        raise ApiError(f"Namava has no {kind} with id {id_}.", 404)
    return doc["result"]


# --- tools ------------------------------------------------------------------------------------------------------


@tool("Search Filimo and Namava")
async def vod_search(
    query: Annotated[
        str,
        Field(
            description="Title words in Persian (or the Latin title for Filimo), e.g. شام ایرانی.",
            min_length=1,
            max_length=100,
        ),
    ],
    site: Annotated[
        Site, Field(description="Which catalog to search; 'both' (default) searches Filimo and Namava.")
    ] = "both",
    kind: Annotated[Kind, Field(description="Only movies, only series, or all.")] = "all",
    limit: Annotated[int, Field(description="Max titles per site.", ge=1, le=20)] = 8,
) -> dict[str, Any]:
    """Search the Filimo and Namava catalogs by title and return matching movies and series with a ref for each.

    Use first when the user names a title. Each hit has a `ref` to pass to vod_title (full details), vod_episodes
    (series seasons and episodes). Use vod_where instead to learn which service has one specific title.
    Filimo hits include year, rating, genres and a summary; Namava search only returns title, kind and year.
    """
    jobs = {}
    if site in ("both", "filimo"):
        jobs["filimo"] = _f_search(query, kind, limit)
    if site in ("both", "namava"):
        jobs["namava"] = _n_search(query, kind, limit)
    return await _gather(jobs, {"query": query})


@tool("Where to watch a title")
async def vod_where(
    title: Annotated[
        str, Field(description="Exact or near-exact title in Persian, e.g. شام ایرانی.", min_length=1, max_length=100)
    ],
    year: Annotated[
        int | None,
        Field(
            description="Production year (Persian calendar like 1403, or Gregorian) to tell remakes apart.",
            ge=1300,
            le=2100,
        ),
    ] = None,
) -> dict[str, Any]:
    """Tell which of Filimo and Namava carries a title, by searching both and matching the title text.

    Use for "is X on Filimo or Namava". Returns the matching titles per site (exact title match first, then titles
    that contain the words) and `available_on`. Only the catalogs are checked, not whether a title needs a
    subscription; use vod_title for that. Pass vod_search results to vod_title for details.
    """
    found = await vod_search(title, "both", "all", 10)
    key = _norm(title)
    out: dict[str, Any] = {"title": title, "available_on": []}
    for s in ("filimo", "namava"):
        hits = found.get(s)
        if hits is None:
            out[s] = "search failed: " + found.get("errors", {}).get(s, "unknown error")
            continue
        exact = [h for h in hits if _norm(h["title"] or "") == key]
        near = [h for h in hits if h not in exact and key and key in _norm(h["title"] or "")]
        if year:
            exact = [h for h in exact if h["year"] in (None, year, year - 621, year - 622)]
        brief = lambda h: {k: h.get(k) for k in ("ref", "title", "title_en", "kind", "year", "url")}  # noqa: E731
        out[s] = {"exact": [brief(h) for h in exact], "similar": [brief(h) for h in near[:5]]}
        if exact:
            out["available_on"].append(s)
    return out


def _n_cast(casts: list[dict[str, Any]]) -> dict[str, list[str]]:
    by: dict[str, list[str]] = {}
    for c in casts or []:
        role = {"actor": "cast", "director": "directors", "author": "writers", "writer": "writers"}.get(
            str(c.get("castRole")).lower()
        )
        if role and c.get("castName") not in by.setdefault(role, []):
            by[role].append(c["castName"])
    by["cast"] = by.get("cast", [])[:15]
    return by


@tool("Title details")
async def vod_title(ref: Ref) -> dict[str, Any]:
    """Get full details of one movie or series on Filimo or Namava: synopsis, genres, year, rating, age rating, cast, director.

    Use after vod_search, vod_browse or vod_new with the `ref` of a hit. For a series, follow with vod_episodes to
    list seasons and episodes; vod_related gives similar titles and vod_person a cast member's filmography. Ratings
    differ per site: Filimo gives stars out of 5 with a vote count and an IMDb score; Namava gives like and dislike
    counts (and an IMDb score for newer titles). Filimo's cast for a movie is the names in its description text; for a
    series it is the actors Filimo features (a few main ones). Namava `people` maps each name to a ref for vod_person.
    """
    site, kind, id_ = _parse_ref(ref)
    if site == "namava":
        d = await _n_detail(kind, id_)
        likes, dislikes = d.get("likeCount") or 0, d.get("dislikeCount") or 0
        out = {
            "site": "namava",
            "ref": ref,
            "title": d.get("caption"),
            "kind": kind,
            "year": d.get("year"),
            "genres": [c["categoryName"] for c in d.get("categories") or []],
            "country": [c["name"] for c in d.get("countryProducers") or []],
            "age_rating": (d.get("ageRange") or {}).get("caption"),
            "age_limit": (d.get("ageRange") or {}).get("value"),
            "summary": _text(d.get("story"), 700),
            "about": _text(d.get("about"), 700),
            "likes": likes,
            "dislikes": dislikes,
            "like_pct": round(100 * likes / (likes + dislikes)) if likes + dislikes else None,
            "imdb": _num(d.get("imdb")),
            "duration_min": d.get("mediaDuration"),
            "hd": d.get("hd") or None,
            "free": d.get("contentPlayAccessType") == "Free",
            # shortcut: only "Free" is marked on the site; "None" is read as paid/subscription, not checked with an account
            "access": "free" if d.get("contentPlayAccessType") == "Free" else "subscription_or_paid",
            "people": {c["castName"]: f"namava:person:{c['castId']}" for c in (d.get("casts") or [])[:20]},
            "persian_dub": d.get("hasPersianDub") or None,
            "persian_subtitle": d.get("hasPersianSubtitle") or None,
            "voices": [v["name"] for v in d.get("voiceList") or []],
            "subtitles": [v.get("name") for v in d.get("subtitleList") or []],
            "image": _n_img(d.get("imageUrl")),
            "url": _n_url(kind, id_, d.get("caption")),
            **_n_cast(d.get("casts")),
        }
        if kind == "series":
            out["season_count"] = d.get("seasonCount")
            out["status"] = d.get("seriesStatus")
        return out
    doc = await fetch(_f_url(f"movie/one/uid/{id_}"))
    g = doc["data"]["attributes"]["General"]
    rate = ((doc["data"]["attributes"].get("action_data") or {}).get("rate") or {}).get("movie") or {}
    series = bool((g.get("serial") or {}).get("enable")) or g.get("pre_title") == "سریال"
    about = g.get("about_movie") or ""
    m = re.search(r"می\u200cتوان\s+(.+?)\s+را نام برد", _text(about, 2000))
    out = {
        "site": "filimo",
        "ref": f"filimo:{id_}",
        "title": g.get("movie_name") or g.get("title"),
        "title_en": g.get("title_en") or None,
        "kind": "series" if series else "movie",
        "year": g.get("pro_year"),
        "genres": [c["title"] for c in g.get("categories") or []],
        "country": [c["title"] for c in g.get("countries") or []],
        "age_rating": g.get("age_range"),
        "rating": rate.get("average"),
        "rating_pct": rate.get("percent"),
        "votes": rate.get("count"),
        "imdb": _num(g.get("imdb_rate")),
        "duration": (g.get("duration") or {}).get("text"),
        "hd": (g.get("HD") or {}).get("enable") or None,
        "persian_dub": (g.get("dubbed") or {}).get("enable") or None,
        "subtitles": (g.get("subtitle") or {}).get("text"),
        "free": bool(g.get("is_free_movie")),
        "directors": [d["name"] for d in g.get("director") or []],
        "cast": [n.strip() for n in re.split(r"[،,]| و ", m.group(1)) if n.strip()] if m else [],
        "image": (g.get("thumbnails") or {}).get("movie_img_b"),
        "url": f"{FILIMO_SITE}/m/{id_}",
    }
    if series:
        # The detail call describes the latest episode; the series' own year, genres and synopsis are in the search row.
        hit = next((i for i in await _f_search(out["title"], "series", 20) if i["ref"] == out["ref"]), None)
        out["votes"] = out["rating"] = out["rating_pct"] = out["imdb"] = out["duration"] = None  # latest-episode values
        if hit:
            out.update(
                {k: hit.get(k) or out.get(k) for k in ("year", "genres", "summary", "rating", "rating_pct", "imdb")}
            )
            out["age_rating"] = hit["age"] or out["age_rating"]
        out["season_count"] = _int(g.get("season_count"))
        out["latest_episode"] = {"title": g.get("title"), "summary": _text(g.get("descr"), 400)}
        try:  # the series' own cast: Filimo names its main actors and writers in the titles of the related rows
            people = _f_people(await _f_related(id_))
        except ApiError:
            people = {"cast": [], "writers": []}
        if people["cast"]:
            out["cast"] = people["cast"]
        out["writers"] = people["writers"]
    else:
        out["summary"] = _text(g.get("descr"), 700)
    return out


@tool("Series seasons and episodes")
async def vod_episodes(
    ref: Ref,
    season: Annotated[
        int | None, Field(description="Season number (1 = first). Default: the latest season.", ge=1, le=60)
    ] = None,
    limit: Annotated[int, Field(description="Max episodes to return.", ge=1, le=100)] = 30,
) -> dict[str, Any]:
    """List the seasons of a series and the episodes of one season (title, summary, length, publish date).

    Use after vod_search or vod_title when the user wants episodes, how many seasons exist or the newest episode.
    Takes a series ref; a movie ref returns an error. Default season is the latest. Streaming links are not provided.
    """
    site, kind, id_ = _parse_ref(ref)
    if site == "namava":
        if kind != "series":
            raise ApiError("That ref is a movie; vod_episodes needs a series ref.")
        d = await _n_detail("series", id_)
        seasons = sorted(
            (
                {"season": _int(s.get("seasonOrderId")), "season_id": s["seasonId"], "name": s.get("seasonName")}
                for s in d.get("seasons") or []
            ),
            key=lambda s: s["season"] or 0,
        )
        if not seasons:
            return {"ref": ref, "title": d.get("caption"), "seasons": [], "episodes": []}
        pick = next((s for s in seasons if s["season"] == season), None) if season else seasons[-1]
        if not pick:
            raise ApiError(f"Season {season} not found; this series has seasons {[s['season'] for s in seasons]}.")
        doc = await fetch(f"{NAMAVA}/v2.0/medias/seasons/{pick['season_id']}/episodes")
        eps = [
            {
                "episode": _int(e.get("episodeCaption")),
                "title": e.get("caption"),
                "summary": _text(e.get("shortDescription"), 250),
                "minutes": e.get("mediaDuration"),
                "published": (e.get("publishDate") or "")[:8] or None,
                "free": True if e.get("contentPlayAccessType") == "Free" else None,
                "url": _n_url("movie", e["id"], e.get("caption")),
            }
            for e in (doc.get("result") or [])[:limit]
        ]
        return {"ref": ref, "title": d.get("caption"), "season": pick["season"], "seasons": seasons, "episodes": eps}
    doc = await fetch(_f_url(f"serial/allseason/uid/{id_}"))
    seasons = [
        {"season": s["serial_season_part"], "name": s.get("title"), "episodes": s.get("cnt")}
        for s in (doc.get("data", {}).get("attributes", {}).get("data") or [])
    ]
    if not seasons:
        raise ApiError("That Filimo title has no seasons; it is a movie. Use vod_title.")
    seasons.sort(key=lambda s: s["season"])
    pick = next((s for s in seasons if s["season"] == season), None) if season else seasons[-1]
    if not pick:
        raise ApiError(f"Season {season} not found; this series has seasons {[s['season'] for s in seasons]}.")
    doc = await fetch(
        _f_url(f"serial/episodebyseason/parent_id/{id_}/part/{pick['season']}/sort/ASC/"),
        {"episode_perpage": min(limit, 40)},
    )
    eps = []
    for _, items in _f_rows_raw(doc):
        for a in items[:limit]:
            eps.append(
                {
                    "episode": _int(a.get("serial_part")),
                    "title": a.get("movie_title"),
                    "summary": _text(a.get("descr"), 250),
                    "minutes": round(int(a["duration"]) / 60) if str(a.get("duration") or "").isdigit() else None,
                    "published": (a.get("publish_date") or "")[:10] or None,
                    "rating": _num(a.get("rate_avrage")),
                    "url": f"{FILIMO_SITE}/m/{a.get('uid')}",
                }
            )
    return {"ref": ref, "season": pick["season"], "seasons": seasons, "episodes": eps[:limit]}


def _f_rows_raw(doc: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Like _f_rows but returns the raw attribute dicts (episodes keep fields _f_item drops)."""
    movies = {str(x["id"]): x["attributes"] for x in doc.get("included", []) if x["type"] == "movies"}
    return [
        (r["attributes"].get("title") or "", [movies[str(m["id"])] for m in ids if str(m["id"]) in movies])
        for r in doc.get("data", [])
        if (ids := r["relationships"].get("movies", {}).get("data"))
    ]


@tool("New releases")
async def vod_new(
    site: Annotated[Site, Field(description="Which catalog; 'both' (default) returns two lists.")] = "both",
    kind: Annotated[Kind, Field(description="Only movies, only series, or all.")] = "all",
    limit: Limit = 12,
) -> dict[str, Any]:
    """List the newest titles added to Filimo and Namava, most recent first.

    Use for "what is new on Filimo/Namava". Filimo lists include year, rating and summary; Namava lists only title
    and kind (call vod_title for more). Use vod_featured for what each site promotes on its front page instead.
    """
    out: dict[str, Any] = {}

    async def filimo():
        rows = _f_rows(await fetch(_f_list(1, kind=kind)))
        # the front page's "تازه\u200cها" row (newest added); the first row is a fallback if Filimo renames it
        items = next((r for t, r in rows if _norm(t) == _norm("تازه\u200cها")), rows[0][1] if rows else [])
        return [i for i in items if kind in ("all", i["kind"])][:limit]

    async def namava():
        doc = await fetch(
            f"{NAMAVA}/v1.0/category-groups/persian/latest-medias", {"pi": 1, "ps": limit if kind == "all" else 40}
        )
        return [i for i in map(_n_item, doc.get("result") or []) if kind in ("all", i["kind"])][:limit]

    if site in ("both", "filimo"):
        out["filimo"] = await filimo()
    if site in ("both", "namava"):
        out["namava"] = await namava()
    return out


@tool("Front-page picks")
async def vod_featured(
    site: Annotated[Site, Field(description="Which catalog; 'both' (default) returns both.")] = "both",
    per_row: Annotated[int, Field(description="Titles per row.", ge=1, le=12)] = 6,
    kind: Annotated[
        Kind,
        Field(
            description="Filimo only: use the Movies page or the Series page rows (the Series page has the popular series row)."
        ),
    ] = "all",
) -> dict[str, Any]:
    """Show what Filimo and Namava promote right now: Filimo's front-page rows (new, popular, box office, genres) and Namava's top slider and top list.

    Use for "what is popular / trending on Filimo or Namava". These are editorial picks, not view counts. Take a
    `ref` from here to vod_title for details. For Namava's most-viewed list use vod_collection(key="namava:popular").
    """
    out: dict[str, Any] = {}
    if site in ("both", "filimo"):
        doc = await fetch(_f_list(1, kind=kind))
        out["filimo"] = [{"row": t, "titles": items[:per_row]} for t, items in _f_rows(doc) if t][:8]
    if site in ("both", "namava"):
        slider = await fetch(f"{NAMAVA}/v3.0/medias/sliders/1316")
        tops = await fetch(f"{NAMAVA}/v1.0/category-groups/tops/latest-medias", {"pi": 1, "ps": per_row})
        out["namava"] = [
            {
                "row": "اسلایدر صفحه اول",
                "titles": [
                    {
                        **_n_item({**x, "name": x.get("caption")}),
                        "year": x.get("year"),
                        "imdb": _num(x.get("imdb")),
                        "summary": _text(x.get("story"), 200),
                    }
                    for x in (slider.get("result") or [])[:per_row]
                ],
            },
            {"row": "برترین\u200cها", "titles": [_n_item(x) for x in (tops.get("result") or [])[:per_row]]},
        ]
    return out


@tool("List genres")
async def vod_genres() -> dict[str, Any]:
    """List the genre names vod_browse accepts for Filimo and Namava, with the English aliases.

    Use before vod_browse when unsure of a genre name. Persian names work for both sites; English aliases such as
    comedy or drama work too. Filimo also takes sort and country filters (see vod_browse).
    """
    return {
        "filimo": [
            {"name": n, "alias": next((e for e, p in FILIMO_EN.items() if p == n), None)} for n in FILIMO_GENRES
        ],
        "namava": [{"name": n, "alias": NAMAVA_EN.get(s) and s} for n, s in NAMAVA_GENRES.items()],
        "filimo_sort": list(FILIMO_SORT),
        "filimo_country": sorted(COUNTRIES),
    }


def _genre(site: str, genre: str) -> Any:
    g = genre.strip().lower()
    if site == "filimo":
        name = FILIMO_EN.get(g) or next((n for n in FILIMO_GENRES if _norm(n) == _norm(genre)), None)
        return FILIMO_GENRES.get(name) if name else None
    name = NAMAVA_ALIASES.get(g) or NAMAVA_ALIASES.get(genre.strip()) or genre.strip()
    name = next((n for n in NAMAVA_GENRES if _norm(n) == _norm(name)), None) or next(
        (n for n, s in NAMAVA_GENRES.items() if s == g), None
    )
    return NAMAVA_GENRES.get(name) if name else None


@tool("Browse by genre")
async def vod_browse(
    genre: Annotated[
        str,
        Field(
            description="Genre name in Persian or English, e.g. کمدی, comedy, درام, documentary. See vod_genres.",
            min_length=1,
            max_length=40,
        ),
    ],
    site: Annotated[Site, Field(description="Which catalog; 'both' (default) returns two lists.")] = "both",
    kind: Annotated[
        Kind, Field(description="Only movies, only series, or all. Namava ignores this and returns both kinds.")
    ] = "all",
    sort: Annotated[
        Literal["default", "newest_added", "year_new", "year_old", "rating", "imdb"],
        Field(description="Filimo only: order of the list. Namava always lists newest first."),
    ] = "default",
    country: Annotated[
        str | None,
        Field(
            description="Filimo only: producer country filter such as iran, america, turkey, s_korea (list in vod_genres)."
        ),
    ] = None,
    page: Annotated[
        int,
        Field(
            description="Page number, 1 = first. Filimo pages reach about 200 titles per filter (5 site pages of 40).",
            ge=1,
            le=50,
        ),
    ] = 1,
    limit: Limit = 15,
) -> dict[str, Any]:
    """List movies and series of one genre on Filimo and Namava, with Filimo's sort and country filters.

    Use for "best comedy series on Filimo", "Iranian dramas", "new documentaries". Filimo rows carry year, rating,
    IMDb and summary; Namava rows only title, kind and id (use vod_title). Next: vod_title or vod_episodes. For themed
    lists (IMDb top 250, Oscar, kids, coming soon) use vod_collections instead.
    """
    if country and country not in COUNTRIES:
        raise ApiError(f"Unknown country '{country}'. Use one of: {', '.join(sorted(COUNTRIES))}.")
    out: dict[str, Any] = {"genre": genre}
    if site in ("both", "filimo"):
        tag = _genre("filimo", genre)
        if tag is None:
            out["filimo"] = f"Filimo has no genre '{genre}'. See vod_genres."
        else:
            items = await _f_pages(tag, kind, FILIMO_SORT[sort], country, page, limit)
            out["filimo"] = [i for i in items or [] if kind in ("all", i["kind"])]
    if site in ("both", "namava"):
        slug = _genre("namava", genre)
        if slug is None:
            out["namava"] = f"Namava has no genre '{genre}' that vod_browse knows. See vod_genres."
        else:
            doc = await fetch(f"{NAMAVA}/v1.0/category-groups/{slug}/latest-medias", {"pi": page, "ps": limit})
            out["namava"] = [_n_item(x) for x in doc.get("result") or []]
    return out


async def _f_person(name: str, limit: int) -> dict[str, Any] | str:
    doc = await fetch(f"{FILIMO}/movie/movie/list/tagid/1000300/text/{quote(name, safe='')}")
    crews = [x["attributes"] for x in doc.get("included", []) if x["type"] == "crews"]
    if not crews:
        return f"Filimo has no person matching '{name}'."
    key = _norm(name)
    c = next((c for c in crews if key in (_norm(c.get("name") or ""), _norm(c.get("name_en") or ""))), crews[0])
    films = await fetch(f"{FILIMO}/movie/movie/list/tagid/1000300/text/{quote(c['name'], safe='')}/fl/crew")
    titles = [i for _, row in _f_rows(films) for i in row]
    born = c.get("birth_date") if c.get("birth_date") not in (None, "", "0000-00-00") else None
    return {
        "name": c["name"],
        "name_en": c.get("name_en") or None,
        "born": born,
        "birth_place": c.get("birth_loc") or None,
        "bio": _text(c.get("bio"), 500),
        "image": c.get("profile_image"),
        "titles": titles[:limit],
        "other_matches": [x["name"] for x in crews if x is not c][:5],
    }


async def _n_person(name: str, limit: int) -> dict[str, Any] | str:
    if m := re.fullmatch(r"namava:person:(\d+)", name):
        id_, others = m.group(1), []
    else:
        doc = await fetch(f"{NAMAVA}/v1.0/search/suggest/{quote(name, safe='')}")
        people = [x for x in (doc.get("result") or {}).get("SuggestList") or [] if x.get("type") == "Cast"]
        if not people:
            return f"Namava has no person matching '{name}'."
        pick = next((x for x in people if _norm(x["name"]) == _norm(name)), people[0])
        id_, others = pick["id"], [x["name"] for x in people if x is not pick][:5]
    d = (await fetch(f"{NAMAVA}/v1.0/casts/{id_}")).get("result")
    if not d:
        raise ApiError(f"Namava has no person with id {id_}.", 404)
    medias = d.get("medias") or []
    return {
        "person": f"namava:person:{id_}",
        "name": d.get("castName"),
        "bio": _text(d.get("fullDescription"), 500),
        "image": _n_img(d.get("imageUrl")),
        "total_titles": len(medias),
        "titles": [_n_item({**x, "id": x.get("mediaId"), "name": x.get("caption")}) for x in medias[:limit]],
        "other_matches": others,
    }


@tool("Actor or director profile")
async def vod_person(
    name: Annotated[
        str,
        Field(
            description="Person's name in Persian (Filimo also takes the Latin name), e.g. پارسا پیروزفر; or a 'namava:person:<id>' ref from vod_title.",
            min_length=2,
            max_length=60,
        ),
    ],
    site: Annotated[Site, Field(description="Which catalog; 'both' (default) looks on Filimo and Namava.")] = "both",
    limit: Annotated[int, Field(description="Max titles per site.", ge=1, le=40)] = 15,
) -> dict[str, Any]:
    """Look up an actor, director or writer on Filimo and Namava: short bio and the titles they appear in.

    Use for "what has X acted in / directed on Filimo or Namava". Titles carry a `ref` for vod_title. Filimo gives
    birth date and place when it has them; Namava gives a bio text. A name matches the first search hit (exact name
    first); `other_matches` lists further people with similar names. Series appear once, not per episode.
    """
    jobs = {}
    if site in ("both", "filimo") and not name.startswith("namava:person:"):
        jobs["filimo"] = _f_person(name, limit)
    if site in ("both", "namava"):
        jobs["namava"] = _n_person(name, limit)
    if not jobs:
        raise ApiError("A namava:person ref only works with site 'namava' or 'both'.")
    return await _gather(jobs, {"query": name})


@tool("Similar titles")
async def vod_related(
    ref: Ref,
    limit: Annotated[int, Field(description="Max similar titles.", ge=1, le=20)] = 12,
) -> dict[str, Any]:
    """List titles similar to one movie or series on Filimo or Namava ("viewers also watch").

    Use after vod_title when the user wants more like it. Filimo also returns its related rows (more by the same
    actors or writer, same genre and decade) and the featured actors and writers; Namava returns one recommendation list.
    Take a `ref` from the result to vod_title.
    """
    site, _, id_ = _parse_ref(ref)
    if site == "namava":
        doc = await fetch(
            f"{NAMAVA}/v2.0/medias/{id_}/recommend-items-anonymous-user", {"isKid": "false", "pi": 1, "ps": limit}
        )
        items = ((doc.get("result") or {}).get("items") or [])[:limit]
        return {"ref": ref, "similar": [_n_item(x) for x in items]}
    rec = _f_rows(await fetch(_f_url(f"movie/recom/uid/{id_}")))
    rows = await _f_related(id_)
    return {
        "ref": ref,
        "similar": (rec[0][1] if rec else [])[:limit],
        "featured_people": _f_people(rows),
        "rows": [{"row": t, "titles": items[:6]} for t, items in rows if t][:6],
    }


async def _n_post_groups() -> list[dict[str, str]]:
    """Curated post groups the Namava site shows on its menu pages (Oscar, true stories, IMDb top ...)."""
    seen: dict[str, str] = {}
    for m in (await fetch(f"{NAMAVA}/v5.0/menus")).get("result") or []:
        for p in m.get("pageItems") or []:
            if p.get("payloadType") == "PostGroup" and p.get("payloadKey") and (p.get("caption") or "").strip():
                seen.setdefault(p["payloadKey"], p["caption"].strip())
    return [{"key": f"namava:post:{k}", "title": v} for k, v in seen.items()]


@tool("List collections")
async def vod_collections(
    site: Annotated[Site, Field(description="Which catalog; 'both' (default) lists both.")] = "both",
) -> dict[str, Any]:
    """List the curated lists vod_collection can open on Filimo and Namava: IMDb top 250, Oscar, kids, coming soon and more.

    Use when the user asks for a themed list (best-of, festival winners, kids, Korean or Turkish series, true stories).
    Each entry has a `key` to pass to vod_collection. Namava category groups (any slug from vod_genres) also work as
    `namava:category:<slug>`.
    """
    out: dict[str, Any] = {}
    if site in ("both", "filimo"):
        out["filimo"] = [{"key": f"filimo:{k}", "title": t} for k, t in FILIMO_LISTS.items()]
    if site in ("both", "namava"):
        out["namava"] = [{"key": f"namava:{k}", "title": t} for k, t in NAMAVA_SPECIAL.items()] + (
            await _n_post_groups()
        )
    return out


@tool("Open a collection")
async def vod_collection(
    key: Annotated[
        str,
        Field(
            description="A key from vod_collections, e.g. 'filimo:imdbtop250', 'filimo:animated_under_15/under_6', 'namava:popular', 'namava:coming_soon', 'namava:post:1437' or 'namava:category:persian'.",
            pattern=r"^(filimo:[A-Za-z0-9_]{1,40}(/[A-Za-z0-9_]{1,30})?|namava:(popular|latest_movies|latest_series|coming_soon|trending|post:\d{1,6}|category:[A-Za-z0-9 -]{2,30}))$",
        ),
    ],
    kind: Annotated[Kind, Field(description="Only movies, only series, or all.")] = "all",
    sort: Annotated[
        Literal["default", "newest_added", "year_new", "year_old", "rating", "imdb"],
        Field(description="Filimo only: order of the list (not for the kids age keys)."),
    ] = "default",
    country: Annotated[
        str | None, Field(description="Filimo only: producer country filter such as iran, turkey (see vod_genres).")
    ] = None,
    page: Annotated[int, Field(description="Page number, 1 = first.", ge=1, le=20)] = 1,
    limit: Limit = 15,
) -> dict[str, Any]:
    """Show the titles of one curated list on Filimo or Namava, such as the IMDb top 250 or coming soon.

    Use after vod_collections. Filimo lists accept sort and country filters and reach about 200 titles; Namava lists
    are fixed (newest or editorial order, `upcoming` marks titles without a release date). The Filimo key 'kids' opens
    the kids home page as several rows. Next: vod_title with a `ref`.
    """
    if country and country not in COUNTRIES:
        raise ApiError(f"Unknown country '{country}'. Use one of: {', '.join(sorted(COUNTRIES))}.")
    site, _, rest = key.partition(":")
    if site == "filimo":
        tag, _, other = rest.partition("/")
        out: dict[str, Any] = {"key": key, "title": FILIMO_LISTS.get(rest)}
        items = await _f_pages(tag, kind, FILIMO_SORT[sort], country, page, limit, other or None)
        if items is None:
            rows = _f_rows(await fetch(_f_list(tag)))
            out["sections"] = [{"row": t, "titles": r[:limit]} for t, r in rows if t][:8]
        else:
            out["titles"] = [i for i in items if kind in ("all", i["kind"])]
        return out
    what, _, arg = rest.partition(":")
    paging = {"pi": page, "ps": limit}
    if what == "category":
        doc = await fetch(f"{NAMAVA}/v1.0/category-groups/{arg}/latest-medias", paging)
    elif what == "post":
        doc = await fetch(f"{NAMAVA}/v2.0/post-groups/{arg}/medias", paging)
    elif what == "coming_soon":
        doc = await fetch(f"{NAMAVA}/v1.0/medias/unknown-date-published/{NAMAVA_COMING_SOON}", paging)
    elif what == "trending":
        doc = await fetch(f"{NAMAVA}/v1.0/search/trends", {"pageCount": limit, "pageIndex": page})
    else:
        doc = await fetch(f"{NAMAVA}/v1.0/medias/{what.replace('_', '-')}", paging)
    title = NAMAVA_SPECIAL.get(what)
    if what == "post":
        title = ((await fetch(f"{NAMAVA}/v1.0/post-groups/{arg}")).get("result") or {}).get("caption")
    soon = {"unknownDatePublish": True} if what == "coming_soon" else {}  # that endpoint omits the flag
    items = [_n_item({**x, **soon}) for x in doc.get("result") or []]
    return {"key": key, "title": title, "titles": [i for i in items if kind in ("all", i["kind"])]}


@tool("Subscription plans")
async def vod_plans() -> dict[str, Any]:
    """Show Namava's public subscription plans and prices (Filimo's prices are not available in its JSON API).

    Use for "how much is a Namava subscription". Prices are in toman before 10% VAT. `price` is the list price,
    `price_new_user` the discounted price shown to new users (what a guest sees); `auto_renew` is the monthly plan that
    renews itself. Filimo shows its prices only in its payment page (https://www.filimo.com/payment).
    """
    doc = (await fetch(f"{NAMAVA}/v2.0/users/subscriptions")).get("result") or {}
    plans = [
        {
            "name": p.get("name"),
            "months": p.get("durationQuantity"),
            "days": p.get("recurringDuration"),
            "tier": (p.get("subscriptionPlanInfo") or {}).get("name"),
            "price": p.get("amount"),
            "price_new_user": p.get("discountAmount"),
            "discount_pct": p.get("discountPercent"),
            "promotion": ((p.get("promotions") or [{}])[0]).get("name"),
            "installments": p.get("isInstallmentProduct") or None,
        }
        for p in doc.get("subscriptionList") or []
    ]
    renew = (await fetch(f"{NAMAVA}/v1.0/direct-debit/subscriptions")).get("result") or []
    return {
        "namava": {
            "plans": plans,
            "auto_renew": [
                {"name": p.get("name"), "days": p.get("recurringDuration"), "price": p.get("amount")} for p in renew
            ],
        },
        "currency": "toman, plus 10% VAT",
        "filimo": "Not in the JSON API; see https://www.filimo.com/payment",
    }
