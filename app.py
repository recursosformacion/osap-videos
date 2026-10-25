from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
import pymysql
import yaml
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = "0.2.4"
LOGGER = logging.getLogger("osap_videos")
sys.path.insert(0, str(BASE_DIR))


def _load_config() -> dict[str, Any]:
    path = Path(os.environ.get("OSAP_VIDEOS_CONFIG", BASE_DIR / "config.yaml"))
    if not path.exists():
        path = BASE_DIR / "config.example.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw.setdefault("db", {})
    raw.setdefault("server", {})
    raw.setdefault("auth", {})
    raw.setdefault("module", {})
    raw["db"]["password"] = os.environ.get(
        "OSAP_VIDEOS_DB_PASSWORD", raw["db"].get("password", "")
    )
    raw["server"]["public_url"] = os.environ.get(
        "OSAP_VIDEOS_PUBLIC_URL", raw["server"].get("public_url", "http://localhost:8400")
    ).rstrip("/")
    raw["auth"]["base_url"] = os.environ.get(
        "OSAP_VIDEOS_AUTH_URL", raw["auth"].get("base_url", "http://127.0.0.1:8200")
    ).rstrip("/")
    raw["module"]["src"] = os.environ.get(
        "AI_YOUTUBE_SRC", raw["module"].get("src", "")
    )
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        key_file = BASE_DIR / "youtube.key"
        if key_file.exists():
            api_key = key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("YOUTUBE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if api_key:
        os.environ["YOUTUBE_API_KEY"] = api_key
    return raw


CONFIG = _load_config()
MODULE_SRC = Path(CONFIG["module"]["src"]).expanduser() if CONFIG["module"].get("src") else None
if MODULE_SRC is None or not MODULE_SRC.is_dir():
    raise RuntimeError("Configura module.src con la ruta a ai_recogeYouTube/src")
sys.path.insert(0, str(MODULE_SRC))

from ai_recogeyoutube.global_search import VOICE_ALIASES, search_global

DB = CONFIG["db"]
AUTH_BASE = CONFIG["auth"]["base_url"]
AUTH_WEB_URL = str(CONFIG["auth"].get("web_url", "https://auth.openmusicrepository.com")).rstrip("/")
PUBLIC_URL = CONFIG["server"]["public_url"]
OSAP_URL = str(CONFIG.get("osap", {}).get("public_url", "https://app.openmusicrepository.com")).rstrip("/")
OSAP_API_BASE = str(CONFIG.get("osap", {}).get("api_url", "http://127.0.0.1:8001/api/v1")).rstrip("/")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema()
    yield


app = FastAPI(title="OSAP Vídeos", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

VOICES = ["all", "song", "soprano", "alto", "tenor", "bass"]
VOICE_LABELS = {
    "unknown": "Voz no indicada",
    "all": "Todas las voces",
    "song": "Obra completa",
    "soprano": "Soprano",
    "alto": "Alto",
    "tenor": "Tenor",
    "bass": "Bajo",
}
MATERIAL_LABELS = {
    "individual_part": "Voz individual",
    "sectional_rehearsal": "Ensayo por cuerdas",
    "full_performance": "Interpretación completa",
    "accompaniment": "Acompañamiento",
    "unknown": "Material no indicado",
}
VOTE_VOICES = {"song", "soprano", "alto", "tenor", "bass"}

STOPWORDS = {
    "the", "and", "for", "with", "from", "los", "las", "del", "una", "uno",
    "por", "con", "para", "que", "como", "sobre", "san", "santa", "saint",
}


@contextmanager
def db() -> Iterator[pymysql.Connection]:
    conn = pymysql.connect(
        host=DB.get("host", "127.0.0.1"),
        port=int(DB.get("port", 3306)),
        user=DB.get("user", "osap2027"),
        password=DB.get("password", ""),
        database=DB.get("name", "osap_videos"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()


def init_schema() -> None:
    schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    with db() as conn:
        with conn.cursor() as cur:
            for statement in schema.split(";"):
                if statement.strip():
                    cur.execute(statement)
        conn.commit()


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def vote_voice(value: str) -> str:
    return value if value in VOTE_VOICES else "unknown"


def tokens(value: str) -> set[str]:
    return {t for t in normalize(value).split() if len(t) > 2 and t not in STOPWORDS}


def similarity(query: str, title: str, channel: str) -> float:
    wanted = tokens(query)
    if not wanted:
        return 0.0
    found = tokens(f"{title} {channel}")
    return round(len(wanted & found) / len(wanted), 4)


def public_user(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        response = httpx.get(
            f"{AUTH_BASE}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    if not data.get("user_id"):
        return None
    return data


def display_name(user: dict[str, Any] | None) -> str:
    if not user:
        return ""
    return str(user.get("name") or user.get("nickname") or user.get("email") or "")


def resource_belongs_to_work(work_id: str, resource_id: str) -> bool:
    try:
        response = httpx.get(
            f"{OSAP_API_BASE}/works/public/{quote(work_id, safe='')}",
            timeout=5.0,
        )
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    representations = data.get("representations") if isinstance(data, dict) else None
    if not isinstance(representations, list):
        return False
    return any(str(rep.get("id")) == resource_id for rep in representations if isinstance(rep, dict))


def vote_counts(resource_id: str, user_id: str | None) -> dict[tuple[str, str], dict[str, int]]:
    if not resource_id:
        return {}
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT video_id, voice,
                       SUM(decision = 'approved') AS approved,
                       SUM(decision = 'rejected') AS rejected
                FROM resource_youtube_votes
                WHERE resource_id = %s
                GROUP BY video_id, voice
                """,
            (resource_id,),
        )
        rows = cur.fetchall()
        mine: dict[tuple[str, str], str] = {}
        if user_id:
            cur.execute(
                """
                    SELECT video_id, voice, decision
                    FROM resource_youtube_votes
                    WHERE resource_id = %s AND user_id = %s
                    """,
                (resource_id, user_id),
            )
            mine = {(r["video_id"], r["voice"]): r["decision"] for r in cur.fetchall()}
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        key = (row["video_id"], row["voice"])
        counts[key] = {
            "approved": int(row["approved"] or 0),
            "rejected": int(row["rejected"] or 0),
            "mine": mine.get(key, ""),
        }
    for key, decision in mine.items():
        counts.setdefault(key, {"approved": 0, "rejected": 0, "mine": decision})
    return counts


def voice_match(text: str, voice: str) -> float:
    aliases = VOICE_ALIASES.get(voice)
    if not aliases:
        return 0.0
    padded = f" {normalize(text)} "
    return 1.0 if any(f" {normalize(alias)} " in padded for alias in aliases) else 0.0


def enrich(
    results: list[dict[str, Any]],
    query: str,
    counts: dict[tuple[str, str], dict[str, int]],
    voice: str,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in results:
        video_id = str(item.get("video_id") or "")
        voice_guess = str(item.get("voice") or "unknown")
        if not video_id or (video_id, voice_guess) in seen:
            continue
        seen.add((video_id, voice_guess))
        count = counts.get((video_id, voice_guess), {})
        title = str(item.get("video_title") or "")
        channel = str(item.get("channel") or "")
        description = str(item.get("description") or "")
        text_score = similarity(query, f"{title} {description[:700]}", channel)
        if voice in {"soprano", "alto", "tenor", "bass"}:
            score = round(text_score * 0.8 + voice_match(f"{title} {description}", voice) * 0.2, 4)
        else:
            score = text_score
        material = str(item.get("material_type") or "unknown")
        enriched.append(
            {
                **item,
                "video_id": video_id,
                "voice": voice_guess,
                "voice_label": VOICE_LABELS.get(voice_guess, "Voz no indicada"),
                "material_label": MATERIAL_LABELS.get(material, ""),
                "material_known": material != "unknown",
                "text_similarity": text_score,
                "voice_match": bool(
                    voice in {"soprano", "alto", "tenor", "bass"}
                    and voice_match(f"{title} {description}", voice)
                ),
                "similarity": score,
                "approved": int(count.get("approved", 0)),
                "rejected": int(count.get("rejected", 0)),
                "mine": str(count.get("mine", "")),
            }
        )
    enriched.sort(
        key=lambda r: (
            -float(r["similarity"]),
            -int(r["approved"]),
            int(r["rejected"]),
            normalize(str(r["video_title"])),
        )
    )
    return enriched


def render(
    request: Request,
    *,
    work_id: str = "",
    resource_id: str = "",
    title: str = "",
    composer: str = "",
    voice: str = "all",
    token: str = "",
    results: list[dict[str, Any]] | None = None,
    error: str = "",
    notice: str = "",
    searched: bool = False,
) -> HTMLResponse:
    user = public_user(token)
    context = {
        "request": request,
        "work_id": work_id,
        "resource_id": resource_id,
        "title": title,
        "composer": composer,
        "voice": voice if voice in VOICES else "all",
        "voices": VOICES,
        "voice_labels": VOICE_LABELS,
        "token": token,
        "user": user,
        "user_name": display_name(user),
        "results": results or [],
        "error": error,
        "notice": notice,
        "searched": searched,
        "authenticated": bool(user),
        "can_vote": bool(user and resource_id),
        "osap_url": OSAP_URL,
        "login_url": f"{AUTH_WEB_URL}/auth/login",
        "register_url": f"{AUTH_WEB_URL}/auth/register",
        "version": APP_VERSION,
        "osap_work_url": f"{OSAP_URL}/obra/{work_id}" if work_id else OSAP_URL,
    }
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/health")
def health() -> dict[str, str]:
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 AS ok")
        cur.fetchone()
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, token: str = "") -> HTMLResponse:
    return render(request, token=token)


@app.get("/works/{work_id}", response_class=HTMLResponse)
def work_page(
    request: Request,
    work_id: str,
    resource: str = "",
    title: str = "",
    composer: str = "",
    voice: str = "all",
    token: str = "",
    voted: str = "",
) -> HTMLResponse:
    notice = {"approved": "Voto positivo registrado.", "rejected": "Voto negativo registrado."}.get(
        voted, ""
    )
    return render(
        request,
        work_id=work_id,
        resource_id=resource,
        title=title,
        composer=composer,
        voice=voice,
        token=token,
        notice=notice,
    )


@app.post("/search", response_class=HTMLResponse)
def search(
    request: Request,
    work_id: str = Form(""),
    resource_id: str = Form(""),
    title: str = Form(""),
    composer: str = Form(""),
    voice: str = Form("all"),
    token: str = Form(""),
) -> HTMLResponse:
    title, composer = title.strip(), composer.strip()
    voice = voice if voice in VOICES else "all"
    if not title and not composer:
        return render(
            request,
            work_id=work_id,
            resource_id=resource_id,
            title=title,
            composer=composer,
            voice=voice,
            token=token,
            error="Escribe al menos el título o el compositor.",
            searched=True,
        )
    query = f"{title} {composer}".strip()
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="osap-videos-"))
        try:
            raw = search_global(
                temp_dir / "search.sqlite3",
                song=title,
                author=composer,
                voice=voice,
                voice_terms=VOICE_ALIASES.get(voice, ()),
                limit=30,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    except (ValueError, RuntimeError) as exc:
        return render(
            request,
            work_id=work_id,
            resource_id=resource_id,
            title=title,
            composer=composer,
            voice=voice,
            token=token,
            error=str(exc),
            searched=True,
        )
    except Exception:
        LOGGER.exception("Fallo inesperado al buscar en YouTube")
        return render(
            request,
            work_id=work_id,
            resource_id=resource_id,
            title=title,
            composer=composer,
            voice=voice,
            token=token,
            error="No se pudo consultar YouTube. Inténtalo de nuevo.",
            searched=True,
        )
    user = public_user(token)
    counts = vote_counts(resource_id, str(user.get("user_id")) if user else None)
    results = enrich(raw, query, counts, voice)
    if tokens(query):
        results = [
            item
            for item in results
            if float(item["text_similarity"]) > 0 or int(item["approved"]) > 0
        ]
    notice = "" if results else "No se han encontrado vídeos relacionados con esta búsqueda."
    return render(
        request,
        work_id=work_id,
        resource_id=resource_id,
        title=title,
        composer=composer,
        voice=voice,
        token=token,
        results=results,
        notice=notice,
        searched=True,
    )


@app.post("/vote", response_model=None)
def vote(
    work_id: str = Form(...),
    resource_id: str = Form(...),
    video_id: str = Form(...),
    voice: str = Form(...),
    decision: str = Form(...),
    video_url: str = Form(""),
    video_title: str = Form(""),
    channel: str = Form(""),
    material_type: str = Form("unknown"),
    similarity_value: str = Form("0"),
    title: str = Form(""),
    composer: str = Form(""),
    token: str = Form(""),
) -> RedirectResponse | HTMLResponse:
    user = public_user(token)
    if not user:
        return HTMLResponse("Necesitas iniciar sesión en OSAP para votar.", status_code=401)
    if decision not in {"approved", "rejected"}:
        return HTMLResponse("Voto no válido.", status_code=400)
    if not resource_belongs_to_work(work_id, resource_id):
        return HTMLResponse("La representación no pertenece a esta obra.", status_code=400)
    voice = vote_voice(voice)
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        similarity_float = float(similarity_value)
    except ValueError:
        similarity_float = 0.0
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO youtube_videos (video_id, url, title, channel, material_type, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    url = VALUES(url), title = VALUES(title), channel = VALUES(channel),
                    material_type = VALUES(material_type)
                """,
                (video_id, video_url, video_title, channel, material_type, now),
            )
            cur.execute(
                """
                INSERT INTO resource_youtube_videos
                    (resource_id, work_id, video_id, voice, search_query, similarity, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    similarity = VALUES(similarity), search_query = VALUES(search_query)
                """,
                (
                    resource_id,
                    work_id,
                    video_id,
                    voice,
                    f"{title} {composer}".strip(),
                    similarity_float,
                    now,
                ),
            )
            cur.execute(
                """
                INSERT INTO resource_youtube_votes
                    (user_id, resource_id, video_id, voice, decision, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    decision = VALUES(decision), updated_at = VALUES(updated_at)
                """,
                (str(user["user_id"]), resource_id, video_id, voice, decision, now, now),
            )
        conn.commit()
    query = {
        "resource": resource_id,
        "title": title,
        "composer": composer,
        "voice": voice,
        "token": token,
        "voted": decision,
    }
    params = urlencode({key: value for key, value in query.items() if value})
    return RedirectResponse(f"/works/{work_id}?{params}", status_code=303)
