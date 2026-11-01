import os

import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_live_search_both(client):
    r = (await client.call_tool("vod_search", {"query": "شام ایرانی", "limit": 5})).structured_content
    assert any(x["title"] == "شام ایرانی" for x in r["filimo"]), r
    assert any(x["ref"] == "namava:series:2377" for x in r["namava"]), r


async def test_live_where_and_title(client):
    r = (await client.call_tool("vod_where", {"title": "شام ایرانی"})).structured_content
    assert r["available_on"] == ["filimo", "namava"], r
    f = (await client.call_tool("vod_title", {"ref": "filimo:0bd4p"})).structured_content
    assert f["title"] == "مرد عینکی" and f["directors"] == ["کریم امینی"] and f["cast"]
    n = (await client.call_tool("vod_title", {"ref": "namava:movie:142977"})).structured_content
    assert n["title"] == "بینوایان" and n["year"] == 1397 and n["cast"]


async def test_live_episodes(client):
    n = (
        await client.call_tool("vod_episodes", {"ref": "namava:series:2377", "season": 16, "limit": 3})
    ).structured_content
    assert n["season"] == 16 and n["episodes"][0]["title"] == "شام ایرانی - فصل ۱۶ قسمت ۱"
    f = (await client.call_tool("vod_episodes", {"ref": "filimo:150570", "season": 1, "limit": 3})).structured_content
    assert f["seasons"][0]["episodes"] == 4 and f["episodes"][0]["title"] == "فصل ۱ قسمت ۱"


async def test_live_new_featured_browse(client):
    r = (await client.call_tool("vod_new", {"limit": 5})).structured_content
    assert len(r["filimo"]) == 5 and len(r["namava"]) == 5
    r = (await client.call_tool("vod_featured", {})).structured_content
    assert r["filimo"] and r["namava"][1]["titles"]
    r = (
        await client.call_tool(
            "vod_browse", {"genre": "کمدی", "kind": "series", "sort": "rating", "country": "iran", "limit": 5}
        )
    ).structured_content
    assert len(r["filimo"]) == 5 and all(x["kind"] == "series" and "کمدی" in x["genres"] for x in r["filimo"]), r
    assert r["namava"]


async def test_live_filimo_genre_ids_still_match():
    from iran_vod_mcp import http
    from iran_vod_mcp.vod import FILIMO_GENRES

    doc = await http.fetch(f"{http.FILIMO}/movie/movie/filter/tagid/1")
    live = {i["title"]: i["tagID"] for a in doc["data"]["attributes"] if a.get("slug") == "parents" for i in a["items"]}
    for name, tag in FILIMO_GENRES.items():
        assert live.get(name) == tag, name


async def test_live_person(client):
    r = (await client.call_tool("vod_person", {"name": "سعید ابوطالب", "limit": 5})).structured_content
    assert r["filimo"]["name_en"] == "Saeid Aboutaleb" and r["filimo"]["titles"], r
    assert r["namava"]["name"] == "سعید ابوطالب" and any(t["title"] == "شام ایرانی" for t in r["namava"]["titles"]), r


async def test_live_related_and_series_cast(client):
    r = (await client.call_tool("vod_related", {"ref": "filimo:150570", "limit": 5})).structured_content
    assert r["similar"] and r["featured_people"]["cast"], r
    f = (await client.call_tool("vod_title", {"ref": "filimo:150570"})).structured_content
    assert f["cast"] == r["featured_people"]["cast"]
    n = (await client.call_tool("vod_related", {"ref": "namava:series:2377", "limit": 5})).structured_content
    assert n["similar"], n


async def test_live_collections_and_paging(client):
    r = (await client.call_tool("vod_collections", {})).structured_content
    assert len(r["filimo"]) > 10 and any(x["key"] == "namava:popular" for x in r["namava"]), r
    if not os.environ.get("IRAN_VOD_MCP_PROXY"):  # the Turkish exit gets no post groups in the menu
        assert any(x["key"].startswith("namava:post:") for x in r["namava"]), r
    if not os.environ.get("IRAN_VOD_MCP_PROXY"):  # foreign titles are hidden from the Turkish exit
        top = (await client.call_tool("vod_collection", {"key": "filimo:imdbtop250", "limit": 5})).structured_content
        assert len(top["titles"]) == 5 and all(t["imdb"] for t in top["titles"]), top
        soon = (await client.call_tool("vod_collection", {"key": "namava:coming_soon", "limit": 3})).structured_content
        assert soon["titles"] and soon["titles"][0]["upcoming"], soon
    # past the 40 titles of the first site page
    p9 = (
        await client.call_tool(
            "vod_browse",
            {
                "genre": "کمدی",
                "site": "filimo",
                "kind": "movie",
                "sort": "rating",
                "country": "iran",
                "page": 9,
                "limit": 5,
            },
        )
    ).structured_content
    assert len(p9["filimo"]) == 5, p9


async def test_live_plans(client):
    r = (await client.call_tool("vod_plans", {})).structured_content
    plans = r["namava"]["plans"]
    assert [p["months"] for p in plans] == [1, 3, 6, 12] and all(p["price"] > 0 for p in plans), r
