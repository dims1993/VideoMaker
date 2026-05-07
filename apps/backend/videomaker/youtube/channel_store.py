"""CRUD para el directorio de canales y sus datos."""

from __future__ import annotations

from typing import Any

from videomaker import db


def upsert_channel(
    *,
    channel_id: str,
    handle: str | None,
    title: str,
    avatar_url: str | None,
) -> None:
    db.execute(
        """
        insert into channels(channel_id, handle, title, avatar_url)
        values (%(channel_id)s, %(handle)s, %(title)s, %(avatar_url)s)
        on conflict (channel_id) do update set
          handle = excluded.handle,
          title = excluded.title,
          avatar_url = excluded.avatar_url,
          updated_at = now();
        """,
        {"channel_id": channel_id, "handle": handle, "title": title or "", "avatar_url": avatar_url},
    )


def set_channel_internal_fields(
    channel_id: str,
    *,
    internal_category: str | None = None,
    notes: str | None = None,
    rpm_estimate: float | None = None,
    monetization_estimate: float | None = None,
) -> None:
    db.execute(
        """
        update channels set
          internal_category = coalesce(%(internal_category)s, internal_category),
          notes = coalesce(%(notes)s, notes),
          rpm_estimate = coalesce(%(rpm_estimate)s, rpm_estimate),
          monetization_estimate = coalesce(%(monetization_estimate)s, monetization_estimate),
          updated_at = now()
        where channel_id = %(channel_id)s
        """,
        {
            "channel_id": channel_id,
            "internal_category": internal_category,
            "notes": notes,
            "rpm_estimate": rpm_estimate,
            "monetization_estimate": monetization_estimate,
        },
    )


def delete_channel(channel_id: str) -> None:
    db.execute("delete from channels where channel_id = %(id)s", {"id": channel_id})


def get_channel(channel_id: str) -> dict[str, Any] | None:
    return db.fetch_one("select * from channels where channel_id = %(id)s", {"id": channel_id})


def upsert_channel_snapshot(
    channel_id: str,
    *,
    subscribers: int | None,
    total_views: int | None,
    video_count: int | None,
) -> None:
    db.execute(
        """
        insert into channel_snapshots(channel_id, subscribers, total_views, video_count)
        values (%(channel_id)s, %(subscribers)s, %(total_views)s, %(video_count)s)
        """,
        {
            "channel_id": channel_id,
            "subscribers": subscribers,
            "total_views": total_views,
            "video_count": video_count,
        },
    )


def list_channel_videos(channel_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    return db.fetch_all(
        """
        select v.*,
          (select hook from video_insights i where i.video_id=v.video_id order by fetched_at desc limit 1) as hook
        from videos v
        where v.channel_id = %(cid)s
        order by published_at desc nulls last
        limit %(limit)s
        """,
        {"cid": channel_id, "limit": limit},
    )


def upsert_videos(channel_id: str, videos: list[dict[str, Any]]) -> None:
    """
    Upsert de vídeos con stats. Espera dicts con claves:
    video_id, title, published_at, duration_s, views, likes, comments, thumbnail_url
    """
    if not videos:
        return
    for v in videos:
        vid = (v.get("video_id") or "").strip()
        if not vid:
            continue
        db.execute(
            """
            insert into videos(video_id, channel_id, title, published_at, duration_s, views, likes, comments, thumbnail_url)
            values (%(video_id)s, %(channel_id)s, %(title)s, %(published_at)s, %(duration_s)s, %(views)s, %(likes)s, %(comments)s, %(thumbnail_url)s)
            on conflict (video_id) do update set
              channel_id = excluded.channel_id,
              title = excluded.title,
              published_at = excluded.published_at,
              duration_s = excluded.duration_s,
              views = excluded.views,
              likes = excluded.likes,
              comments = excluded.comments,
              thumbnail_url = excluded.thumbnail_url;
            """,
            {
                "video_id": vid,
                "channel_id": channel_id,
                "title": v.get("title") or "",
                "published_at": v.get("published_at"),
                "duration_s": v.get("duration_s"),
                "views": v.get("views"),
                "likes": v.get("likes"),
                "comments": v.get("comments"),
                "thumbnail_url": v.get("thumbnail_url"),
            },
        )


def insert_video_insights(video_id: str, insights: dict[str, Any]) -> None:
    if not video_id:
        return
    db.execute(
        """
        insert into video_insights(video_id, hook, outline_json, broll_themes_json, cta, keywords_json)
        values (%(video_id)s, %(hook)s, %(outline)s, %(broll)s, %(cta)s, %(keywords)s)
        """,
        {
            "video_id": video_id,
            "hook": insights.get("hookPattern") or insights.get("hook") or None,
            "outline": insights.get("sectionOutline"),
            "broll": insights.get("suggestedBrollThemes"),
            "cta": insights.get("CTAStyle") or insights.get("cta") or None,
            "keywords": insights.get("keywordOpportunities"),
        },
    )


def list_channels(
    *,
    q: str = "",
    category: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = (q or "").strip()
    category = (category or "").strip()
    limit = max(1, min(int(limit), 200))
    where = []
    params: dict[str, Any] = {"limit": limit}
    if q:
        where.append("(title ilike %(q)s or handle ilike %(q)s or channel_id ilike %(q)s)")
        params["q"] = f"%{q}%"
    if category:
        where.append("internal_category = %(cat)s")
        params["cat"] = category
    wsql = ("where " + " and ".join(where)) if where else ""
    return db.fetch_all(
        f"""
        select c.*,
          (select subscribers from channel_snapshots s where s.channel_id=c.channel_id order by fetched_at desc limit 1) as subscribers,
          (select total_views from channel_snapshots s where s.channel_id=c.channel_id order by fetched_at desc limit 1) as total_views,
          (select video_count from channel_snapshots s where s.channel_id=c.channel_id order by fetched_at desc limit 1) as video_count
        from channels c
        {wsql}
        order by updated_at desc
        limit %(limit)s
        """,
        params,
    )

