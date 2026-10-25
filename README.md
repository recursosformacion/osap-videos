# OSAP Videos

Independent companion application for OpenMusicRepository (OSAP). It finds YouTube videos for a
work representation, plays them in place, and lets signed-in OSAP users vote whether a video is
useful for that representation and voice.

**Status: experimental technical preview.** It is deployed at
`https://videos.openmusicrepository.com`, but it is not a finished product and it is not part of
the coordinated OSAP `5.7.0` release; that release only adds links to this app. Expect API, data model, and authentication changes.

## What works

- Live YouTube search using the `ai-recogeYouTube` module, including localized voice terms\n  (bass/bajo/baix/basse/basso…).
- Results ordered by community votes and textual similarity.
- In-page YouTube player; users do not need to leave the result page to listen.
- Votes (`useful` / `not useful`) stored in MySQL per representation, video, and voice.
- Authentication delegated to `osap-auth`; the application does not store passwords.
- OSAP work and representation links can prefill the work title, composer, and resource.
- The application checks with the public OSAP API that a representation belongs to the work
  before accepting a vote.

## What does not work or is not finished

- **Authentication handoff is temporary.** The OSAP access token travels in the query string
  so server-rendered forms can use it. That exposes it to browser history, logs, and `Referer`
  headers. It must be replaced by a one-time handoff or a short-lived `HttpOnly` cookie before
  this application is treated as production-grade.
- There is no CSRF protection, rate limiting, abuse detection, moderation queue, or admin UI
  for removing videos and votes.
- Search results are not persisted. Only videos that receive a vote are stored, together with
  their representation relation.
- Work-level videos are not voted independently: a vote always belongs to a representation.
- The module's SQLite database is ephemeral and per search. MySQL is the source of truth for
  videos, relations, and votes.
- There are no automated database backups or retention jobs specific to this application.
- YouTube API quota is shared by searches; searches are not cached across users.
- The test suite covers the pure action rules, not a full authenticated voting flow.
- The application has no published SLA and runs as a single local process.

## Architecture

```text
OSAP spa / public work page
        │  link with work, resource, title, composer, token
        ▼
videos.openmusicrepository.com  (FastAPI + Jinja, port 8400)
        │
        ├── osap-auth /auth/me                (token validation)
        ├── osap-api /works/public/{id}       (resource belongs to work)
        ├── ai-recogeYouTube global_search    (live YouTube search)
        └── MySQL osap_videos                 (videos, relations, votes)
```

## Quick start (development)

Requirements: Python 3.11+, MySQL/MariaDB, and the `ai-recogeYouTube` source tree.

```powershell
Copy-Item config.example.yaml config.yaml
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e ..\ai_recogeYouTube
$env:YOUTUBE_API_KEY = "..."
.\.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8400
```

Create the database and configure `config.yaml` first:

```sql
CREATE DATABASE osap_videos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The schema is created on startup from `schema.sql`. Health check:
`http://127.0.0.1:8400/health`.

## Tests

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

## Configuration

`config.yaml` is git-ignored. Start from `config.example.yaml` and set:

- `db.*`: MySQL connection; use `OSAP_VIDEOS_DB_PASSWORD` in production.
- `auth.base_url`: internal `osap-auth` URL.
- `osap.public_url`: public OSAP URL for links.
- `osap.api_url`: internal OSAP API URL used to validate representations.
- `module.src`: path to `ai-recogeYouTube/src`.
- `YOUTUBE_API_KEY`: environment variable, `youtube.key`, or `.env`.

## OSAP integration

Build the OSAP web app with:

```powershell
$env:VITE_VIDEOS_URL = "https://videos.openmusicrepository.com"
npm run build
```

Without that variable, the OSAP build points the video buttons at
`http://localhost:8400`. The button is only useful when the videos application is running.

## Deployment

The repository contains `deploy/osap-videos.service` and `deploy/nginx-videos.conf`. The current
server layout is:

- Code and virtual environment: `/opt/osap-videos`.
- Internal port: `8400`, bound to `127.0.0.1`.
- systemd unit: `osap-videos.service`, user `ocw`.
- Nginx server name: `videos.openmusicrepository.com`, TLS via Let's Encrypt.

Secrets live only in `/opt/osap-videos/.env` and `config.yaml`; neither is committed.

## Versioning

The application version is **0.2.0** and is independent from the coordinated OSAP version.
OSAP **5.7.0** (B) publishes the video entry points. The videos application itself remains
**0.2.0** and experimental; the two versions are intentionally independent.

---

# OSAP Vídeos — estado real

Aplicativo independiente para buscar y votar vídeos de YouTube asociados a una obra y a una
representación de OSAP.

## Estado

Desplegado como **preview técnica** en `https://videos.openmusicrepository.com`. No es todavía
una pieza de producción equiparable a los cuatro servicios principales de OSAP: no tiene
handoff de autenticación definitivo, ni moderación, ni copias de seguridad propias, ni SLA.

La versión del aplicativo es **0.2.0**. OSAP **5.7.0** (B) publica los enlaces desde la
plataforma; la versión de la app se mantiene independiente y experimental.

## Qué hace

- Busca en YouTube con el módulo `ai-recogeYouTube`, incluyendo la voz en varios idiomas\n  (bajo, bass, baix, basse, basso…).
- Ordena por votos de la comunidad y similitud textual.
- Permite escuchar dentro de la página.
- Guarda votos en MySQL por representación, vídeo y voz.
- Valida el token contra `osap-auth` y que la representación pertenezca a la obra contra la API
  pública de OSAP.

## Límites conocidos

- El token de OSAP viaja en la URL. Es una solución temporal y no debe considerarse segura.
- No hay CSRF, rate limiting, moderación ni panel de administración.
- Solo se guardan los vídeos votados; las búsquedas no se persisten.
- No hay voto a nivel de obra sin representación.
- El SQLite del módulo es efímero; la fuente de verdad es MySQL.
- No hay backup ni retención específicos de `osap_videos`.
- La cuota de YouTube se consume en cada búsqueda.
- El flujo completo de voto autenticado no tiene prueba automatizada.

## Puesta en marcha

1. Copiar `config.example.yaml` a `config.yaml`.
2. Crear la base `osap_videos`.
3. Definir `YOUTUBE_API_KEY`.
4. Instalar dependencias y arrancar `uvicorn app:app --host 127.0.0.1 --port 8400`.

El esquema se crea al arrancar. Health: `http://127.0.0.1:8400/health`.

## Despliegue

- Servicio `osap-videos.service` en `/opt/osap-videos`, usuario `ocw`.
- Nginx `videos.openmusicrepository.com` con TLS de Let's Encrypt.
- Secretos en `/opt/osap-videos/.env`; no se versionan.
- El build de OSAP necesita `VITE_VIDEOS_URL` para enlazar a este aplicativo.

## Pruebas

```powershell
python -m pytest tests -q
```

### Repetir el despliegue

```powershell
pwsh deploy/update.ps1
```

El script empaqueta la app y `ai-recogeYouTube`, actualiza `/opt/osap-videos`, instala
dependencias y reinicia `osap-videos.service`. No toca `config.yaml`, `.env`, MySQL ni nginx.
El primer despliegue (base de datos, systemd, nginx y certificado) se hace una sola vez y se
documenta en el historial operativo; las actualizaciones usan ese script.
