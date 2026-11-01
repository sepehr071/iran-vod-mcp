<!-- mcp-name: io.github.sepehr071/iran-vod-mcp -->

<div align="center">

# iran-vod-mcp: Filimo (فیلیمو) and Namava (نماوا) catalog MCP server for AI agents

**iran-vod-mcp is an unofficial, read-only MCP server that gives AI agents the public movie and series catalogs of Filimo and Namava.**<br>
Its 13 tools search both services, tell you which one carries a title, read synopsis, rating, cast and age rating,<br>
list seasons and episodes, look up actors and directors, find similar titles, open curated lists (IMDb top 250, Oscar, kids,<br>
coming soon), browse genres and show Namava subscription prices.<br>
No API key or account is needed. It works in Claude, Cursor, Copilot and any other MCP client.

[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/iran-vod-mcp/blob/main/LICENSE)

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

</div>

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for filimo.com and namava.ir, the two big Iranian video-on-demand services: title search, "which service has this title", title details, series seasons and episodes, actor and director filmographies, similar titles, curated lists, new releases, front-page picks, genre browsing, Namava plans.
- **Install:** `uvx iran-vod-mcp` or `claude mcp add iran-vod -- uvx iran-vod-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none. Optional `IRAN_VOD_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only catalog data. It cannot log in, play video, give stream links or change anything, so no confirmation is needed before calling any tool.
- **Tools:** 13, all prefixed `vod_`. Typical sequences: `vod_search` -> `vod_title` -> `vod_episodes` / `vod_related` / `vod_person`; `vod_where` for one title; `vod_browse` -> `vod_title`; `vod_collections` -> `vod_collection`.
- **Use when:** the user asks if a film or series is on Filimo or Namava, what it is about, who is in it, its rating or age rating, how many seasons or episodes it has, what is new or popular, or what to watch in a genre.
- **Do not use when:** the user wants to watch, download or get stream links, or needs Filimo prices (only Namava plans are public JSON).
- **Output:** compact JSON. Years are Persian-calendar as the sites show them (foreign titles show the Gregorian year). Ratings differ: Filimo stars out of 5 with a vote count and IMDb, Namava like and dislike counts. Text is Persian site content.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/iran-vod-mcp/blob/main/server.json).

## Quick start

```bash
claude mcp add iran-vod -- uvx iran-vod-mcp
```

Or in any MCP client config:

```json
{ "mcpServers": { "iran-vod": { "command": "uvx", "args": ["iran-vod-mcp"] } } }
```

Both sites answer from Iran directly. Foreign (licensed) titles are only listed to Iranian IP addresses: from abroad you
see the Iranian catalog only. If you need a proxy, set `IRAN_VOD_MCP_PROXY=http://host:port`.

## Tools

| Tool | What it does |
|---|---|
| `vod_search` | Search Filimo, Namava or both by title; movies and series with a `ref` each |
| `vod_where` | Which of the two services carries a title (exact and similar matches per site) |
| `vod_title` | Synopsis, genres, year, rating, age rating, country, cast and director of one title |
| `vod_episodes` | Seasons of a series and the episodes of one season (summary, length, date) |
| `vod_new` | Newest titles per service, movies or series |
| `vod_featured` | What each front page promotes: Filimo rows (popular, box office, genres), Namava hero slider and top list |
| `vod_browse` | Titles of one genre; Filimo also sorts (rating, IMDb, year, newest added) and filters by country |
| `vod_genres` | Genre names, aliases, sort and country values |
| `vod_person` | An actor or director: bio and the titles they appear in, on Filimo and Namava |
| `vod_related` | Titles similar to one title; Filimo also names its featured actors and writers |
| `vod_collections` | Curated lists you can open: IMDb top 250, festival winners, kids, Oscar, true stories, coming soon |
| `vod_collection` | The titles of one curated list (Filimo sort and country filters, paging to about 200 titles) |
| `vod_plans` | Namava subscription plans and prices (Filimo prices are not in its JSON API) |

Example prompts:

- "Is Iranian Dinner (شام ایرانی) on Filimo or Namava, and how many seasons?"
- "Best-rated Iranian comedy series on Filimo."
- "What is new on Namava this week?"
- "What has Parsa Pirouzfar acted in on Filimo?" / "What is coming soon to Namava?"
- <span dir="rtl">فیلم بینوایان در نماوا هست؟ کارگردانش کیست؟</span>
- <span dir="rtl">سریال‌های ایرانی با بیشترین امتیاز در فیلیمو کدامند؟</span>

## FAQ

**Can it play or download videos?** No. It lists and describes titles only; no stream or download URLs are fetched.

**Why do I see fewer titles from abroad?** Both services hide licensed foreign titles from non-Iranian IP addresses.

**Why does a Filimo series show only a few actors?** Filimo has no cast list. For a movie the names come from its
description text; for a series they are the actors Filimo features on the series page (usually two or three).

**Is it affiliated with Filimo or Namava?** No. It reads the same public JSON the websites use, at a polite rate with a short cache.

## فارسی

<div dir="rtl">

`iran-vod-mcp` یک سرور MCP غیررسمی و فقط‌خواندنی برای فهرست فیلم و سریال فیلیمو و نماوا است: جستجوی عنوان در هر دو سرویس،
اینکه یک عنوان در کدام سرویس هست، خلاصه داستان، امتیاز، رده سنی، بازیگران، فصل‌ها و قسمت‌ها، تازه‌ها و دسته‌بندی ژانر.
پخش، دانلود و ورود به حساب پشتیبانی نمی‌شود. نصب: `uvx iran-vod-mcp`

</div>

## License

MIT. Author: Sepehr Radmard (سپهر رادمرد), [github.com/sepehr071](https://github.com/sepehr071), [linkedin.com/in/sepehr-radmard](https://linkedin.com/in/sepehr-radmard).
