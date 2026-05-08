"""CRUD para el directorio de canales y sus datos."""

from __future__ import annotations

import json
from typing import Any

from videomaker import db


def upsert_channel(
    *,
    channel_id: str,
    handle: str | None,
    title: str,
    avatar_url: str | None,
    description: str | None = None,
) -> None:
    db.execute(
        """
        insert into channels(channel_id, handle, title, avatar_url, description)
        values (%(channel_id)s, %(handle)s, %(title)s, %(avatar_url)s, %(description)s)
        on conflict (channel_id) do update set
          handle = excluded.handle,
          title = excluded.title,
          avatar_url = excluded.avatar_url,
          description = excluded.description,
          updated_at = now();
        """,
        {
            "channel_id": channel_id,
            "handle": handle,
            "title": title or "",
            "avatar_url": avatar_url,
            "description": (description or None),
        },
    )


def mark_channel_pearl(channel_id: str, *, is_pearl: bool) -> None:
    if not channel_id:
        return
    db.execute(
        """
        update channels set
          is_pearl = %(is_pearl)s,
          updated_at = now()
        where channel_id = %(id)s
        """,
        {"id": channel_id, "is_pearl": bool(is_pearl)},
    )


def touch_channel_synced(channel_id: str) -> None:
    if not channel_id:
        return
    db.execute(
        """
        update channels set
          last_synced_at = now(),
          updated_at = now()
        where channel_id = %(id)s
        """,
        {"id": channel_id},
    )


def set_channel_internal_fields(
    channel_id: str,
    *,
    internal_category: str | None = None,
    notes: str | None = None,
    language: str | None = None,
    rpm_estimate: float | None = None,
    monetization_estimate: float | None = None,
) -> None:
    db.execute(
        """
        update channels set
          internal_category = coalesce(%(internal_category)s, internal_category),
          notes = coalesce(%(notes)s, notes),
          language = coalesce(%(language)s, language),
          rpm_estimate = coalesce(%(rpm_estimate)s, rpm_estimate),
          monetization_estimate = coalesce(%(monetization_estimate)s, monetization_estimate),
          updated_at = now()
        where channel_id = %(channel_id)s
        """,
        {
            "channel_id": channel_id,
            "internal_category": internal_category,
            "notes": notes,
            "language": language,
            "rpm_estimate": rpm_estimate,
            "monetization_estimate": monetization_estimate,
        },
    )


def delete_channel(channel_id: str) -> None:
    db.execute("delete from channels where channel_id = %(id)s", {"id": channel_id})


def get_channel(channel_id: str) -> dict[str, Any] | None:
    return db.fetch_one("select * from channels where channel_id = %(id)s", {"id": channel_id})


def get_channels_internal_fields(channel_ids: list[str]) -> dict[str, dict[str, Any]]:
    ids = [c for c in (channel_ids or []) if c]
    if not ids:
        return {}
    rows = db.fetch_all(
        """
        select channel_id, internal_category, language, is_pearl
        from channels
        where channel_id = any(%(ids)s)
        """,
        {"ids": ids},
    )
    return {r["channel_id"]: r for r in rows}


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


def list_channel_videos_detail(channel_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    return db.fetch_all(
        """
        select
          v.*,
          -- Derived metrics:
          greatest(1.0, extract(epoch from (now() - v.published_at)) / 86400.0) as age_days,
          case
            when v.published_at is null then null
            else (coalesce(v.views,0)::float / greatest(1.0, extract(epoch from (now() - v.published_at)) / 86400.0))
          end as views_per_day,
          case
            when v.published_at is null then null
            else (coalesce(v.views,0)::float / greatest(1.0, extract(epoch from (now() - v.published_at)) / 3600.0))
          end as vph,
          case when coalesce(v.views,0) <= 0 then null else (coalesce(v.likes,0)::float / v.views::float) end as like_rate,
          case when coalesce(v.views,0) <= 0 then null else (coalesce(v.comments,0)::float / v.views::float) end as comment_rate,
          case when coalesce(v.views,0) <= 0 then null else ((coalesce(v.likes,0)+coalesce(v.comments,0))::float / v.views::float) end as engagement,
          (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1) as channel_subscribers,
          case
            when (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1) is null
              or (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1) <= 0
            then null
            else ((coalesce(v.likes,0)+coalesce(v.comments,0))::float / (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1)::float)
          end as engagement_per_sub
        from videos v
        where v.channel_id = %(cid)s
        order by published_at desc nulls last
        limit %(limit)s
        """,
        {"cid": channel_id, "limit": limit},
    )


def list_channel_videos_detail_by_ids(channel_id: str, *, video_ids: list[str]) -> list[dict[str, Any]]:
    """
    Like list_channel_videos_detail, but filtered to an explicit set of video_ids.
    Preserves DB-derived metrics for those rows.
    """
    ids = [v.strip() for v in (video_ids or []) if v and v.strip()]
    if not ids:
        return []
    # hard cap to avoid huge IN lists
    ids = ids[:200]
    return db.fetch_all(
        """
        select
          v.*,
          -- Derived metrics:
          greatest(1.0, extract(epoch from (now() - v.published_at)) / 86400.0) as age_days,
          case
            when v.published_at is null then null
            else (coalesce(v.views,0)::float / greatest(1.0, extract(epoch from (now() - v.published_at)) / 86400.0))
          end as views_per_day,
          case
            when v.published_at is null then null
            else (coalesce(v.views,0)::float / greatest(1.0, extract(epoch from (now() - v.published_at)) / 3600.0))
          end as vph,
          case when coalesce(v.views,0) <= 0 then null else (coalesce(v.likes,0)::float / v.views::float) end as like_rate,
          case when coalesce(v.views,0) <= 0 then null else (coalesce(v.comments,0)::float / v.views::float) end as comment_rate,
          case when coalesce(v.views,0) <= 0 then null else ((coalesce(v.likes,0)+coalesce(v.comments,0))::float / v.views::float) end as engagement,
          (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1) as channel_subscribers,
          case
            when (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1) is null
              or (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1) <= 0
            then null
            else ((coalesce(v.likes,0)+coalesce(v.comments,0))::float / (select subscribers from channel_snapshots s where s.channel_id=v.channel_id order by fetched_at desc limit 1)::float)
          end as engagement_per_sub
        from videos v
        where v.channel_id = %(cid)s
          and v.video_id = any(%(ids)s)
        """,
        {"cid": channel_id, "ids": ids},
    )


def upsert_videos(channel_id: str, videos: list[dict[str, Any]]) -> None:
    """
    Upsert de vídeos con stats. Espera dicts con claves:
    video_id, title, published_at, duration_s, views, likes, comments, thumbnail_url,
    description, tags_json (or tags), category_id, default_language, default_audio_language
    """
    if not videos:
        return
    for v in videos:
        vid = (v.get("video_id") or "").strip()
        if not vid:
            continue
        tags_val = v.get("tags_json") if v.get("tags_json") is not None else (v.get("tags") or None)
        # psycopg no serializa automáticamente listas/dicts a JSONB con placeholders pyformat.
        # Normalizamos a texto JSON para jsonb.
        if tags_val is not None and not isinstance(tags_val, (str, bytes)):
            tags_val = json.dumps(tags_val, ensure_ascii=False)
        db.execute(
            """
            insert into videos(
              video_id, channel_id, title, published_at, duration_s, views, likes, comments, thumbnail_url,
              description, tags_json, category_id, default_language, default_audio_language
            )
            values (
              %(video_id)s, %(channel_id)s, %(title)s, %(published_at)s, %(duration_s)s, %(views)s, %(likes)s, %(comments)s, %(thumbnail_url)s,
              %(description)s, %(tags_json)s, %(category_id)s, %(default_language)s, %(default_audio_language)s
            )
            on conflict (video_id) do update set
              channel_id = excluded.channel_id,
              title = excluded.title,
              published_at = excluded.published_at,
              duration_s = excluded.duration_s,
              views = excluded.views,
              likes = excluded.likes,
              comments = excluded.comments,
              thumbnail_url = excluded.thumbnail_url,
              description = excluded.description,
              tags_json = excluded.tags_json,
              category_id = excluded.category_id,
              default_language = excluded.default_language,
              default_audio_language = excluded.default_audio_language;
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
                "description": v.get("description") or "",
                "tags_json": tags_val,
                "category_id": v.get("category_id") or None,
                "default_language": v.get("default_language") or None,
                "default_audio_language": v.get("default_audio_language") or None,
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


def list_channels_opportunities(
    *,
    q: str = "",
    category: str = "",
    limit: int = 50,
    pearls_only: bool = True,
    # filters
    min_subs: int | None = None,
    min_views: int | None = None,
    min_uploads_month: float | None = None,
    min_views_per_sub: float | None = None,
    min_hit_rate: float | None = None,
    # config
    window_videos: int = 50,
    hit_views_threshold: int = 50_000,
    # sorting
    sort: str = "opportunity",
) -> list[dict[str, Any]]:
    q = (q or "").strip()
    category = (category or "").strip()
    limit = max(1, min(int(limit), 200))
    window_videos = max(5, min(int(window_videos), 200))
    hit_views_threshold = max(1, int(hit_views_threshold))

    params: dict[str, Any] = {
        "limit": limit,
        "pearls_only": bool(pearls_only),
        "q_has": bool(q),
        "q": f"%{q}%" if q else "",
        "cat_has": bool(category),
        "cat": category or "",
        "min_subs_has": min_subs is not None,
        "min_subs": int(min_subs) if min_subs is not None else 0,
        "min_views_has": min_views is not None,
        "min_views": int(min_views) if min_views is not None else 0,
        "min_uploads_month_has": min_uploads_month is not None,
        "min_uploads_month": float(min_uploads_month) if min_uploads_month is not None else 0.0,
        "min_views_per_sub_has": min_views_per_sub is not None,
        "min_views_per_sub": float(min_views_per_sub) if min_views_per_sub is not None else 0.0,
        "min_hit_rate_has": min_hit_rate is not None,
        "min_hit_rate": float(min_hit_rate) if min_hit_rate is not None else 0.0,
        "window_videos": window_videos,
        "hit_views_threshold": hit_views_threshold,
        "sort": (sort or "opportunity").strip().lower(),
    }

    # We compute metrics from:
    # - last snapshot (latest)
    # - 30d/90d snapshot (latest <= now()-interval)
    # - last N videos stored per channel (ordered by published_at desc)
    return db.fetch_all(
        """
        with base as (
          select c.*
          from channels c
          where (not %(q_has)s or (c.title ilike %(q)s or c.handle ilike %(q)s or c.channel_id ilike %(q)s))
            and (not %(cat_has)s or c.internal_category = %(cat)s)
            and (not %(pearls_only)s or coalesce(c.is_pearl,false) = true)
        ),
        snap_latest as (
          select distinct on (s.channel_id)
            s.channel_id, s.fetched_at,
            s.subscribers::bigint as subscribers,
            s.total_views::bigint as total_views,
            s.video_count::int as video_count
          from channel_snapshots s
          join base b on b.channel_id = s.channel_id
          order by s.channel_id, s.fetched_at desc
        ),
        snap_30d as (
          select distinct on (s.channel_id)
            s.channel_id, s.fetched_at,
            s.subscribers::bigint as subscribers_30d,
            s.total_views::bigint as total_views_30d
          from channel_snapshots s
          join base b on b.channel_id = s.channel_id
          where s.fetched_at <= now() - interval '30 days'
          order by s.channel_id, s.fetched_at desc
        ),
        snap_90d as (
          select distinct on (s.channel_id)
            s.channel_id, s.fetched_at,
            s.subscribers::bigint as subscribers_90d,
            s.total_views::bigint as total_views_90d
          from channel_snapshots s
          join base b on b.channel_id = s.channel_id
          where s.fetched_at <= now() - interval '90 days'
          order by s.channel_id, s.fetched_at desc
        ),
        v_ranked as (
          select
            v.*,
            row_number() over (partition by v.channel_id order by v.published_at desc nulls last) as rn
          from videos v
          join base b on b.channel_id = v.channel_id
        ),
        v_win as (
          select *
          from v_ranked
          where rn <= %(window_videos)s
        ),
        v_aggs as (
          select
            channel_id,
            count(*)::int as videos_in_window,
            max(published_at) as last_upload_at,
            -- engagement sums
            sum(coalesce(views,0))::bigint as sum_views,
            sum(coalesce(likes,0))::bigint as sum_likes,
            sum(coalesce(comments,0))::bigint as sum_comments,
            -- median views/duration
            percentile_cont(0.5) within group (order by coalesce(views,0)) as median_views,
            percentile_cont(0.5) within group (order by coalesce(duration_s,0)) as median_duration_s,
            -- hit rate
            avg(case when coalesce(views,0) >= %(hit_views_threshold)s then 1.0 else 0.0 end) as hit_rate,
            -- variability proxy (stddev on log(views+1) reduces outliers)
            stddev_pop(ln(coalesce(views,0) + 1.0)) as views_log_stddev,
            -- cadence: uploads per month (90d window)
            (count(*) filter (where published_at >= now() - interval '90 days'))::float / 3.0 as uploads_per_month_90d,
            -- longform ratios
            avg(case when coalesce(duration_s,0) >= 8*60 then 1.0 else 0.0 end) as pct_over_8min,
            avg(case when coalesce(duration_s,0) >= 10*60 then 1.0 else 0.0 end) as pct_over_10min
          from v_win
          group by channel_id
        ),
        metrics as (
          select
            b.*,
            sl.subscribers,
            sl.total_views,
            sl.video_count,
            -- velocity deltas (null if missing older snapshot)
            case when s30.subscribers_30d is null or sl.subscribers is null then null else (sl.subscribers - s30.subscribers_30d) end as subs_delta_30d,
            case when s90.subscribers_90d is null or sl.subscribers is null then null else (sl.subscribers - s90.subscribers_90d) end as subs_delta_90d,
            case when s30.total_views_30d is null or sl.total_views is null then null else (sl.total_views - s30.total_views_30d) end as views_delta_30d,
            case when s90.total_views_90d is null or sl.total_views is null then null else (sl.total_views - s90.total_views_90d) end as views_delta_90d,
            case when s30.subscribers_30d is null or s30.subscribers_30d <= 0 or sl.subscribers is null then null else ((sl.subscribers - s30.subscribers_30d)::float / s30.subscribers_30d::float) end as subs_growth_pct_30d,
            case when s30.total_views_30d is null or s30.total_views_30d <= 0 or sl.total_views is null then null else ((sl.total_views - s30.total_views_30d)::float / s30.total_views_30d::float) end as views_growth_pct_30d,
            -- efficiency
            case when sl.subscribers is null or sl.subscribers <= 0 or sl.total_views is null then null else (sl.total_views::float / sl.subscribers::float) end as views_per_sub,
            case when sl.video_count is null or sl.video_count <= 0 or sl.total_views is null then null else (sl.total_views::float / sl.video_count::float) end as views_per_video_alltime,
            -- window metrics
            va.videos_in_window,
            va.median_views,
            va.hit_rate,
            va.views_log_stddev,
            va.uploads_per_month_90d,
            case when va.last_upload_at is null then null else extract(epoch from (now() - va.last_upload_at)) / 86400.0 end as days_since_last_upload,
            case when va.sum_views <= 0 then null else (va.sum_likes::float / va.sum_views::float) * 1000.0 end as likes_per_1k_views,
            case when va.sum_views <= 0 then null else (va.sum_comments::float / va.sum_views::float) * 1000.0 end as comments_per_1k_views,
            (va.median_duration_s::float / 60.0) as median_duration_min,
            va.pct_over_8min,
            va.pct_over_10min
          from base b
          left join snap_latest sl on sl.channel_id = b.channel_id
          left join snap_30d s30 on s30.channel_id = b.channel_id
          left join snap_90d s90 on s90.channel_id = b.channel_id
          left join v_aggs va on va.channel_id = b.channel_id
        ),
        filtered as (
          select *
          from metrics m
          where (not %(min_subs_has)s or coalesce(m.subscribers,0) >= %(min_subs)s)
            and (not %(min_views_has)s or coalesce(m.total_views,0) >= %(min_views)s)
            and (not %(min_uploads_month_has)s or coalesce(m.uploads_per_month_90d,0) >= %(min_uploads_month)s)
            and (not %(min_views_per_sub_has)s or coalesce(m.views_per_sub,0) >= %(min_views_per_sub)s)
            and (not %(min_hit_rate_has)s or coalesce(m.hit_rate,0) >= %(min_hit_rate)s)
        ),
        scored as (
          select
            f.*,
            -- Simple, transparent score (can be tuned later).
            (
              -- velocity: prefer 30d views delta and subs delta (scaled)
              (coalesce(f.views_delta_30d,0)::float / 1000000.0)
              + (coalesce(f.subs_delta_30d,0)::float / 10000.0)
              -- efficiency
              + (coalesce(f.views_per_sub,0)::float / 1000.0)
              -- consistency
              + (coalesce(f.hit_rate,0)::float * 2.0)
              -- engagement
              + (coalesce(f.comments_per_1k_views,0)::float / 10.0)
              + (coalesce(f.likes_per_1k_views,0)::float / 50.0)
              -- longform monetization proxy
              + (coalesce(f.pct_over_8min,0)::float * 1.0)
              + (coalesce(f.pct_over_10min,0)::float * 1.0)
              -- penalty for inactivity
              - (coalesce(f.days_since_last_upload,0)::float / 120.0)
            ) as opportunity_score
          from filtered f
        )
        select *
        from scored
        order by
          case when %(sort)s = 'opportunity' then opportunity_score end desc nulls last,
          case when %(sort)s = 'subs_delta_30d' then subs_delta_30d end desc nulls last,
          case when %(sort)s = 'views_delta_30d' then views_delta_30d end desc nulls last,
          case when %(sort)s = 'median_views' then median_views end desc nulls last,
          case when %(sort)s = 'hit_rate' then hit_rate end desc nulls last,
          case when %(sort)s = 'engagement' then comments_per_1k_views end desc nulls last,
          case when %(sort)s = 'uploads_per_month' then uploads_per_month_90d end desc nulls last,
          case when %(sort)s = 'days_since_upload' then days_since_last_upload end asc nulls last,
          case when %(sort)s = 'views_per_sub' then views_per_sub end desc nulls last,
          updated_at desc
        limit %(limit)s
        """,
        params,
    )


