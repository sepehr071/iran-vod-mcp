import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

F = "/api/fa/v1/movie/"
N = "/api/"
TOOLS = {
    "vod_search",
    "vod_where",
    "vod_title",
    "vod_episodes",
    "vod_new",
    "vod_featured",
    "vod_genres",
    "vod_browse",
    "vod_person",
    "vod_related",
    "vod_collections",
    "vod_collection",
    "vod_plans",
}


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name
        assert all("title" not in p for p in t.input_schema.get("properties", {}).values()), t.name


async def test_search_merges_both_sites(client, api):
    api[F + "movie/list/tagid/1000300/text/شام ایرانی"] = fixture("f_search.json")
    api[N + "v5.0/search/advance"] = fixture("n_search.json")
    r = (await client.call_tool("vod_search", {"query": "شام ایرانی", "limit": 2})).structured_content
    f, n = r["filimo"], r["namava"]
    assert [x["ref"] for x in f] == ["filimo:150570", "filimo:6988"]
    assert f[0]["kind"] == "series" and f[0]["year"] == 1403 and f[0]["rating"] == 4.1 and "drama" not in f[0]
    assert (
        n[0]["ref"] == "namava:series:2377"
        and n[0]["year"] == 1390
        and n[0]["url"] == "https://www.namava.ir/series/2377-شام_ایرانی"
    )
    q = api.calls[-1].url.params if "advance" in api.calls[-1].url.path else api.calls[0].url.params
    assert q["query"] == "شام ایرانی" and q["type"] == "all"


async def test_search_survives_one_site_down(client, api):
    api[F + "movie/list/tagid/1000300/text/x"] = fixture("f_search.json")
    r = (await client.call_tool("vod_search", {"query": "x"})).structured_content  # namava route missing -> 404
    assert r["filimo"] and "namava" in r["errors"] and "namava" not in r


async def test_where_matches_exact_title_per_site(client, api):
    api[F + "movie/list/tagid/1000300/text/شام ایرانی"] = fixture("f_search.json")
    api[N + "v5.0/search/advance"] = fixture("n_search.json")
    r = (await client.call_tool("vod_where", {"title": "شام ایرانی"})).structured_content
    assert r["available_on"] == ["filimo", "namava"]
    assert {x["ref"] for x in r["filimo"]["exact"]} == {"filimo:150570", "filimo:6988"}
    r = (await client.call_tool("vod_where", {"title": "شام ایرانی", "year": 1390})).structured_content
    assert [x["ref"] for x in r["filimo"]["exact"]] == ["filimo:6988"]


async def test_namava_movie_details(client, api):
    api[N + "v2.0/medias/142977/single-movie"] = fixture("n_movie.json")
    r = (await client.call_tool("vod_title", {"ref": "namava:movie:142977"})).structured_content
    assert r["title"] == "بینوایان" and r["year"] == 1397 and r["genres"][0] == "درام"
    assert r["directors"] == ["حسین پارسایی"]
    assert r["cast"][0] == "پارسا پیروزفر" and r["like_pct"] == 90 and r["free"] is True
    assert r["age_rating"].startswith("نمایش محتوا") and r["duration_min"] == 93
    assert api.calls[0].headers["x-application-type"] == "WebClient"


async def test_namava_series_details_have_seasons_count(client, api):
    api[N + "v2.0/medias/2377/single-series"] = fixture("n_series.json")
    r = (await client.call_tool("vod_title", {"ref": "namava:series:2377"})).structured_content
    assert r["kind"] == "series" and r["season_count"] == 16 and r["directors"] == ["سعید ابوطالب"]


async def test_filimo_movie_details_pull_cast_from_description(client, api):
    api[F + "movie/one/uid/0bd4p"] = fixture("f_movie.json")
    r = (await client.call_tool("vod_title", {"ref": "filimo:0bd4p"})).structured_content
    assert r["title"] == "مرد عینکی" and r["year"] == 1404 and r["kind"] == "movie"
    assert r["rating"] == 4.28 and r["votes"] == 190630 and r["imdb"] == 3.9
    assert r["directors"] == ["کریم امینی"] and r["cast"][:2] == ["بهرام افشاری", "مهدی هاشمی"] and len(r["cast"]) == 8
    assert r["genres"] == ["کمدی", "اکشن"] and r["age_rating"] == "15-18"


async def test_filimo_series_details_use_series_name(client, api):
    api[F + "movie/one/uid/150570"] = fixture("f_series_one2.json")
    api[F + "movie/list/tagid/1000300/text/شام ایرانی"] = fixture("f_search.json")
    api[F + "movie/related/movieid/150570"] = fixture("f_related.json")
    r = (await client.call_tool("vod_title", {"ref": "filimo:150570"})).structured_content
    assert r["title"] == "شام ایرانی" and r["kind"] == "series" and r["season_count"] == 11
    assert r["year"] == 1403 and r["rating"] == 4.1 and "votes" not in r and r["summary"].startswith("«شام ایرانی»")
    assert "قسمت آخر" in r["latest_episode"]["title"]
    # the series' own cast comes from the "بازی\u200cهای <actor>" related rows, not from the latest episode text
    assert r["cast"] == ["بهنوش بختیاری", "پژمان بازغی", "یوسف تیموری"]


async def test_namava_episodes_default_to_latest_season(client, api):
    api[N + "v2.0/medias/2377/single-series"] = fixture("n_series.json")
    api[N + "v2.0/medias/seasons/81060/episodes"] = fixture("n_episodes.json")
    r = (await client.call_tool("vod_episodes", {"ref": "namava:series:2377", "season": 16})).structured_content
    assert r["season"] == 16 and [e["episode"] for e in r["episodes"]] == [1, 2, 3]
    assert r["episodes"][0]["minutes"] == 64 and r["episodes"][0]["free"] is True
    bad = await client.call_tool("vod_episodes", {"ref": "namava:series:2377", "season": 40})
    assert bad.is_error and "seasons" in bad.content[0].text


async def test_namava_movie_ref_is_rejected_for_episodes(client, api):
    r = await client.call_tool("vod_episodes", {"ref": "namava:movie:142977"})
    assert r.is_error and "movie" in r.content[0].text


async def test_filimo_episodes(client, api):
    api[F + "serial/allseason/uid/150570"] = fixture("f_allseason.json")
    api[F + "serial/episodebyseason/parent_id/150570/part/1/sort/ASC/"] = fixture("f_episodes.json")
    r = (await client.call_tool("vod_episodes", {"ref": "filimo:150570", "season": 1, "limit": 3})).structured_content
    assert len(r["seasons"]) == 11 and r["seasons"][0]["episodes"] == 4
    assert [e["episode"] for e in r["episodes"]] == [1, 2, 3] and r["episodes"][0]["minutes"] == 71
    assert api.calls[-1].url.params["episode_perpage"] == "3"


async def test_filimo_movie_has_no_seasons(client, api):
    api[F + "serial/allseason/uid/0bd4p"] = {"data": {"type": "Serial", "attributes": {"data": []}}}
    r = await client.call_tool("vod_episodes", {"ref": "filimo:0bd4p"})
    assert r.is_error and "movie" in r.content[0].text


async def test_new_lists_both_sites_and_filters_kind(client, api):
    api[F + "movie/list/tagid/1"] = fixture("f_new.json")
    api[N + "v1.0/category-groups/persian/latest-medias"] = fixture("n_latest.json")
    r = (await client.call_tool("vod_new", {"limit": 3})).structured_content
    assert len(r["filimo"]) == 3 and len(r["namava"]) == 3
    r = (await client.call_tool("vod_new", {"site": "namava", "kind": "movie", "limit": 3})).structured_content
    assert "filimo" not in r and all(x["kind"] == "movie" for x in r["namava"])


async def test_featured(client, api):
    api[F + "movie/list/tagid/1"] = fixture("f_home.json")
    api[N + "v3.0/medias/sliders/1316"] = fixture("n_slider.json")
    api[N + "v1.0/category-groups/tops/latest-medias"] = fixture("n_latest.json")
    r = (await client.call_tool("vod_featured", {"per_row": 2})).structured_content
    assert r["filimo"][0]["row"] and len(r["filimo"][0]["titles"]) == 2
    assert [x["row"] for x in r["namava"]] == ["اسلایدر صفحه اول", "برترین\u200cها"]
    assert r["namava"][0]["titles"][0]["title"] == "گنگستر" and r["namava"][0]["titles"][0]["year"] == 1405


async def test_browse_builds_filimo_filters_and_picks_genre_row(client, api):
    # Filimo's "load more" endpoint pages the main list; its filter segment is <country>-<sort>-<type>
    more = F + "movie/loadmore/tagid/1000060/more_type/infinity/other_data/iran-user_rate-movie/show_serial_parent/1"
    api[F + "movie/list/tagid/1000060/other_data/movie-user_rate-iran"] = fixture("f_browse.json")  # holds the link
    api[more + "/perpage/40/page/1"] = fixture("f_more.json")
    api[more + "/perpage/40/page/2"] = {"data": [], "included": []}
    api[N + "v1.0/category-groups/comedy/latest-medias"] = fixture("n_latest.json")
    r = (
        await client.call_tool(
            "vod_browse",
            {"genre": "comedy", "kind": "movie", "sort": "rating", "country": "iran", "page": 2, "limit": 2},
        )
    ).structured_content
    assert [x["title"] for x in r["filimo"]] == ["مدرسه پیرمردها", "اجاره نشین ها"]  # items 3-4
    assert all(x["kind"] == "movie" for x in r["filimo"])
    assert [x["rating"] for x in r["filimo"]] == sorted((x["rating"] for x in r["filimo"]), reverse=True)
    assert r["namava"][0]["ref"].startswith("namava:")
    q = api.calls[-1].url.params
    assert q["pi"] == "2" and q["ps"] == "2"


async def test_browse_filimo_runs_on_to_the_next_site_page(client, api):
    api[F + "movie/list/tagid/1000060"] = {"data": []}  # no paged row: the load-more url is built from the filters
    base = F + "movie/loadmore/tagid/1000060/more_type/infinity/show_serial_parent/1/perpage/40"
    api[base + "/page/1"] = fixture("f_more.json")
    api[base + "/page/2"] = fixture("f_browse.json")
    r = (
        await client.call_tool("vod_browse", {"genre": "کمدی", "site": "filimo", "page": 2, "limit": 4})
    ).structured_content
    assert len(r["filimo"]) == 4 and r["filimo"][0]["title"] != "مرد آفتابی"  # items 5-8 come from site page 2
    assert api.calls[-1].url.path.endswith("/page/2")


async def test_browse_unknown_genre_and_country(client, api):
    r = (await client.call_tool("vod_browse", {"genre": "نامعلوم"})).structured_content
    assert "no genre" in r["filimo"] and "no genre" in r["namava"] and not api.calls
    r = await client.call_tool("vod_browse", {"genre": "کمدی", "country": "mars"})
    assert r.is_error and "country" in r.content[0].text


async def test_genre_aliases_resolve():
    from iran_vod_mcp.vod import _genre

    assert _genre("filimo", "Comedy") == 1000060 and _genre("filimo", "علمی تخیلی") == 1000059
    assert _genre("namava", "هیجان انگیز") == "thriller" and _genre("namava", "animation") == "anime-animation"
    assert _genre("namava", "وحشت") == "horror" and _genre("namava", "horror") == "horror"
    assert _genre("namava", "نامعلوم") is None


async def test_genres_listing(client):
    r = (await client.call_tool("vod_genres", {})).structured_content
    assert any(g["name"] == "کمدی" for g in r["filimo"]) and any(g["name"] == "درام" for g in r["namava"])
    assert "rating" in r["filimo_sort"] and "iran" in r["filimo_country"]


async def test_bad_ref_is_rejected(client):
    r = await client.call_tool("vod_title", {"ref": "netflix:123"})
    assert r.is_error


async def test_namava_genres_added_in_round_two():
    from iran_vod_mcp.vod import _genre

    assert _genre("namava", "short") == "short-movie" and _genre("namava", "reality-tv") == "reality show"
    assert _genre("namava", "دوبله نماوا") == "exclisuve-dubs" and _genre("namava", "education") == "education"


async def test_person_on_both_sites(client, api):
    api[F + "movie/list/tagid/1000300/text/بهنوش بختیاری"] = fixture("f_person_search.json")
    api[F + "movie/list/tagid/1000300/text/بهنوش بختیاری/fl/crew"] = fixture("f_person_films.json")
    api[N + "v1.0/search/suggest/بهنوش بختیاری"] = {"succeeded": True, "result": {"SuggestList": []}}
    r = (await client.call_tool("vod_person", {"name": "بهنوش بختیاری", "limit": 3})).structured_content
    f = r["filimo"]
    assert f["name"] == "بهنوش بختیاری" and f["name_en"] == "Behnoosh Bakhtiari" and f["born"] and f["bio"]
    assert len(f["titles"]) == 3 and all(t["ref"].startswith("filimo:") for t in f["titles"])
    assert not any(" - فصل" in t["title"] for t in f["titles"])  # episodes collapse to the series name
    assert "no person" in r["namava"]


async def test_person_namava_by_ref_and_by_name(client, api):
    api[N + "v1.0/casts/7763"] = fixture("n_cast.json")
    r = (await client.call_tool("vod_person", {"name": "namava:person:7763", "limit": 2})).structured_content
    n = r["namava"]
    assert "filimo" not in r and n["name"] == "هومن برق نورد" and n["total_titles"] == 4 and len(n["titles"]) == 2
    assert n["titles"][0]["ref"].startswith("namava:") and "bio" in n
    api[N + "v1.0/search/suggest/سعید ابوطالب"] = fixture("n_suggest.json")
    api[N + "v1.0/casts/75352"] = fixture("n_cast.json")
    r = (await client.call_tool("vod_person", {"name": "سعید ابوطالب", "site": "namava"})).structured_content
    assert r["namava"]["person"] == "namava:person:75352"
    bad = await client.call_tool("vod_person", {"name": "namava:person:7763", "site": "filimo"})
    assert bad.is_error


async def test_namava_title_links_people(client, api):
    api[N + "v2.0/medias/2377/single-series"] = fixture("n_series.json")
    r = (await client.call_tool("vod_title", {"ref": "namava:series:2377"})).structured_content
    assert r["people"]["هومن برق نورد"] == "namava:person:7763" and r["access"] == "free"


async def test_related_filimo_and_namava(client, api):
    api[F + "movie/recom/uid/150570"] = fixture("f_recom.json")
    api[F + "movie/one/uid/150570"] = fixture("f_series_one2.json")
    api[F + "movie/related/movieid/150570"] = fixture("f_related.json")
    r = (await client.call_tool("vod_related", {"ref": "filimo:150570", "limit": 2})).structured_content
    assert len(r["similar"]) == 2 and r["featured_people"]["cast"][0] == "بهنوش بختیاری"
    assert r["rows"][0]["row"].startswith("بازی") and r["rows"][0]["titles"]
    api[N + "v2.0/medias/2377/recommend-items-anonymous-user"] = fixture("n_recommend.json")
    r = (await client.call_tool("vod_related", {"ref": "namava:series:2377"})).structured_content
    assert len(r["similar"]) == 3 and r["similar"][0]["ref"].startswith("namava:series:")
    assert api.calls[-1].url.params["isKid"] == "false"


async def test_collections_list_and_open(client, api):
    api[N + "v5.0/menus"] = fixture("n_menus.json")
    r = (await client.call_tool("vod_collections", {})).structured_content
    assert {"key": "filimo:imdbtop250", "title": "250 فیلم برتر IMDB"} in r["filimo"]
    keys = [x["key"] for x in r["namava"]]
    assert "namava:popular" in keys and "namava:coming_soon" in keys and any(k.startswith("namava:post:") for k in keys)
    link = "https://www.filimo.com" + F + "movie/loadmore/tagid/603/more_type/infinity/other_data/imdb_rate-imdb_rate"
    row = {
        "type": "Row",
        "id": 1,
        "attributes": {"more_type": "infinity", "links": {"self": link + "/perpage/40/page/1"}},
    }
    api[F + "movie/list/tagid/imdbtop250"] = {"data": [{**row, "relationships": {}}]}  # named lists page another tag
    base = (
        F + "movie/loadmore/tagid/603/more_type/infinity/other_data/imdb_rate-imdb_rate/show_serial_parent/1/perpage/40"
    )
    api[base + "/page/1"] = fixture("f_more.json")
    r = (await client.call_tool("vod_collection", {"key": "filimo:imdbtop250", "limit": 2})).structured_content
    assert r["title"] == "250 فیلم برتر IMDB" and [x["title"] for x in r["titles"]] == ["مرد آفتابی", "دلداده"]
    api[N + "v1.0/medias/unknown-date-published/1384"] = fixture("n_post_medias.json")
    r = (await client.call_tool("vod_collection", {"key": "namava:coming_soon", "limit": 3})).structured_content
    assert r["titles"][0]["upcoming"] is True and r["titles"][0]["ref"].startswith("namava:")
    api[N + "v2.0/post-groups/1437/medias"] = fixture("n_post_medias.json")
    api[N + "v1.0/post-groups/1437"] = fixture("n_post_group.json")
    r = (await client.call_tool("vod_collection", {"key": "namava:post:1437"})).structured_content
    assert r["title"] and r["titles"]
    bad = await client.call_tool("vod_collection", {"key": "filimo:../x"})
    assert bad.is_error


async def test_collection_without_paged_row_returns_sections(client, api):
    api[F + "movie/loadmore/tagid/kids/more_type/infinity/show_serial_parent/1/perpage/40/page/1"] = {"data": []}
    api[F + "movie/list/tagid/kids"] = fixture("f_home.json")
    r = (await client.call_tool("vod_collection", {"key": "filimo:kids", "limit": 2})).structured_content
    assert r["sections"] and len(r["sections"][0]["titles"]) == 2


async def test_plans(client, api):
    api[N + "v2.0/users/subscriptions"] = fixture("n_plans.json")
    api[N + "v1.0/direct-debit/subscriptions"] = fixture("n_direct_debit.json")
    r = (await client.call_tool("vod_plans", {})).structured_content
    p = r["namava"]["plans"][0]
    assert p["months"] == 1 and p["price"] == 190000 and p["price_new_user"] == 161500
    assert r["namava"]["auto_renew"][0]["price"] == 140000 and "filimo" in r


async def test_requests_look_like_each_sites_own_frontend(api):
    from iran_vod_mcp import http

    api["/api/v5.0/menus"] = {}
    api["/api/fa/v1/movie/movie/list/tagid/1"] = {}
    await http.fetch("https://www.namava.ir/api/v5.0/menus")
    await http.fetch("https://www.filimo.com/api/fa/v1/movie/movie/list/tagid/1")
    nv, fl = (c.headers for c in api.calls)
    assert nv["accept"] == "application/json, text/plain, */*" and nv["x-application-type"] == "WebClient"
    assert nv["x-client-version"] and nv["x-is-iframe"] == "false" and "origin" not in nv
    assert fl["accept"] == "*/*" and fl["content-type"] == "application/json"
    assert (
        fl["trackerabtest"].startswith('{"leadToApp"')
        and "useragent" not in fl
        and "origin" not in fl
        and fl["sec-fetch-site"] == "same-origin"
    )
