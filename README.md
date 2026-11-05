# Quiz Arena

A real-time quiz competition platform with a Romanian interface. An administrator creates competitions and editions, authors single- or multiple-choice questions, and controls exactly when every participant sees the next question. Email accounts have exactly two roles, **ADMIN** and **USER**. Participants can also use the original guest flow with a display name and edition password.

The experience follows an administrator-led quiz format: everyone sees the same question; the administrator can pause, resume, advance, or finish early. **Only correctness affects points. Response speed never adds points or breaks ties.**

## Architecture

```mermaid
flowchart LR
    B[React / Vite browser] -->|REST /api/v1| N[Nginx]
    B <-->|Authenticated WebSocket /ws| N
    N --> A[FastAPI · one worker]
    A --> P[(SQLite / PostgreSQL)]
```

- **Frontend:** React 19, TypeScript, Vite, React Router, Tailwind CSS 4, TanStack Query, React Hook Form, Zod, Lucide icons.
- **Backend:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, SQLite for local startup or PostgreSQL, Alembic, Argon2id.
- **Infrastructure:** Docker Compose, PostgreSQL 18 with a named persistent volume, a Python backend container, and a multi-stage frontend build served through Nginx. Only Nginx exposes a host port.
- **Tests:** pytest against file-backed SQLite or actual PostgreSQL, Vitest/Testing Library, and a Playwright browser acceptance test.

The database owns all competition state. WebSockets send edition-scoped event notifications; clients immediately fetch an authorized REST snapshot. This avoids leaking answer keys or another participant's session in broadcast messages. There is no polling loop and no automatic question timer. Heartbeats detect broken sockets, with exponential reconnect and snapshot reload.

## Quick start with Docker

Prerequisites: Docker Engine/Desktop with Docker Compose v2. Docker Desktop must be running.

On Windows PowerShell, generate an ignored `.env` with cryptographically random passwords:

```powershell
.\scripts\setup.ps1
docker compose up --build
```

On another platform, copy `.env.example` to `.env`, replace both example passwords with strong random secrets, and run `docker compose up --build`.

- Application: **http://localhost:8080**
- Administrator: **http://localhost:8080/admin/login**
- API documentation: **http://localhost:8080/api/docs**
- Health check: **http://localhost:8080/api/v1/health**

Sign in at `/login` with `ADMIN_EMAIL` (default `admin@example.com`) and `ADMIN_PASSWORD` from `.env`. The initial admin is created only if no ADMIN account exists. Its initial password must have at least 12 characters. Changing `.env` later does not overwrite an existing admin's credentials. `ADMIN_USERNAME` is retained for compatibility with the previous admin API. `/admin/login` redirects to the shared email login page.

On upgrade, the existing administrator, password hash, IDs, quizzes and sessions are preserved. The first migrated administrator receives `admin@example.com`; additional legacy administrators receive `admin-<id>@example.com`. Use the trusted CLI below to replace these addresses with real emails. A pre-upgrade development backup is stored in ignored `.local/backups/before-accounts.dump` in the implementation workspace.

The backend runs migrations before startup. Service health checks ensure PostgreSQL is ready before migrations and the API is ready before Nginx. Data and opaque session records survive `docker compose restart` and `docker compose down`. **`docker compose down -v` deliberately deletes the database volume.**

## Online deployment

To publish the application on the internet, see [DEPLOY.md](DEPLOY.md). The root `Dockerfile` builds a single container (frontend + API on one port), and `render.yaml` is a one-click Render Blueprint with a persistent SQLite disk.

## Local Windows development without Docker

Prerequisites: Python 3.12+, Node.js 22.12+ or 24, and npm. SQLite is included with Python; no database server installation is needed.

```powershell
.\scripts\start-local.ps1
```

This installs dependencies, checks the database, creates the SQLite file **`.local/quiz.sqlite3`** and its tables if missing, creates the initial admin, and starts FastAPI and Vite as hidden background processes. Existing data and admin credentials are retained on subsequent starts. Ports 8000 and 5173 must be available.

The API also initializes the database automatically when started directly with `uvicorn app.main:app`. An initial `ADMIN_PASSWORD` of at least 12 characters is required; `scripts/setup.ps1` generates it in `.env`. A malformed or incompatible database causes a clear startup error and is never silently replaced. SQLite schema versions are checked; future schema changes need explicit SQLite migration support.

SQLite uses WAL, foreign keys, a 30-second lock wait and serialized transactions (`BEGIN IMMEDIATE`) to preserve answer/START/NEXT atomicity. Run **one backend worker on one machine**, with the file on a local disk. A test covers 60 simultaneous answer transactions; this is not a guarantee for arbitrary hardware or traffic. Back up the file while the application is stopped, or use SQLite's backup API.

For the original local PostgreSQL setup, install PostgreSQL 16/17/18 and run `scripts/start-local.ps1 -PostgreSQL` (add `-SkipInstall` when appropriate). Docker Compose continues to use PostgreSQL. Existing PostgreSQL competitions/accounts are not automatically copied to SQLite; use `-PostgreSQL` to keep using them. An explicit `DATABASE_URL` overrides the default SQLite location.

To show frontend and backend logs in two separate terminal windows, use `scripts/start-local.ps1 -VisibleTerminals`. Add `-SkipInstall` when dependencies are already installed and unchanged.

- Application: **http://localhost:5173**
- API: **http://127.0.0.1:8000/api/docs**
- Logs: `.local/backend-error.log`, `.local/frontend.log`, `.local/dev-postgres.log`
- Admin credentials: `.env`

```powershell
.\scripts\stop-local.ps1
```

Stop preserves database files. Start the app again with `start-local.ps1`. In PostgreSQL mode, do not change the database password in `.env` without also changing the database role password.

### Test through VS Code port forwarding

In VS Code's **Ports** panel, forward **5173**, then copy the generated HTTPS forwarded address. The local startup script uses 5173; port 8080 is for Docker Compose and will return a tunnel error if no service is listening there.

Restart local development with the exact forwarded origin:

```powershell
.\scripts\stop-local.ps1
.\scripts\start-local.ps1 -SkipInstall -TunnelUrl "https://YOUR-TUNNEL-5173.euw.devtunnels.ms"
```

Replace the example with the address copied from VS Code. The option permits that specific hostname in Vite and adds the exact origin to the backend's write and WebSocket checks. Only forward 5173: Vite already proxies `/api` and `/ws` to the backend. Restart with the new URL if VS Code changes the tunnel address. A private tunnel requires signing in with the account used in VS Code; choose Public only if you want access without that tunnel sign-in.

For manual development on any OS, install `backend` with `pip install -e './backend[test]'`, provide `DATABASE_URL=postgresql+psycopg://...`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `APP_ORIGINS` in the process environment, then run in `backend/`:

```sh
alembic upgrade head
python -m app.bootstrap
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In `frontend/`, run `npm ci` and `npm run dev`. Vite proxies `/api` and `/ws` to `127.0.0.1:8000`.

## Configuration

| Variable | Meaning |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` | Compose database credentials; password is mandatory. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Initial admin email/password; password is mandatory on first initialization. |
| `ADMIN_USERNAME` | Legacy admin username, retained for existing API integrations. |
| `APP_ORIGINS` | Comma-separated exact allowed browser origins, including scheme and port. No wildcard. |
| `COOKIE_SECURE` | `false` for local HTTP; **`true` when deployed over HTTPS**. |
| `WEB_PORT` | Compose web port, default `8080`. Update `APP_ORIGINS` when changing this. |
| `DATABASE_URL` | Optional SQLite or PostgreSQL URL; overrides separate `DB_*` variables. Without a URL or DB_HOST, SQLite is used. |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Backend database connection; Compose sets these automatically. |
| `SESSION_DAYS` | USER account and participant cookie lifetime, default 30 days. Admin sessions last 12 hours. |

For LAN access, expose the web service on your network and add the actual origin (for example `http://192.168.1.10:8080`) to `APP_ORIGINS`. Distribute participant links using that address. For an internet deployment, terminate HTTPS at a reverse proxy, forward WebSocket Upgrade headers, set `COOKIE_SECURE=true`, and set your exact HTTPS origin. Nginx here serves HTTP behind that TLS terminator.

## Usage

1. Sign in at `/login` with an ADMIN account.
2. Create a competition and an edition. Set an edition password of at least eight characters.
3. Add questions, choose their type, add/remove options, and mark the correct choices. Single-choice requires exactly one correct option; multiple-choice requires at least two. Reorder questions with the arrow buttons.
4. Open **Control live** and choose **Deschide înscrierile**. Copy the edition link and share it together with the password.
5. Participants enter their names and the password, then see the waiting room. Names are unique within an edition after whitespace and Unicode normalization and case folding.
6. Press **START CONCURS** and confirm. Registration closes atomically and the first question appears for everyone. Questions and edition settings are now locked.
7. Watch the response count. Press **Următoarea întrebare** whenever ready. Participants cannot navigate between questions. Answers to closed questions are rejected, including delayed manual API requests.
8. At the last question, choose **Finalizează concursul** and confirm. Results and correct answers become available. Previous editions remain accessible in the admin interface. **Încheie anticipat** can also finish a LIVE or PAUSED edition at any question, with confirmation; unanswered questions score zero.

During LIVE, **Pune pe pauză** blocks answer submission and NEXT while retaining the active question and already submitted answers. **Reia concursul** restores answering for the same question. Question text/options/order and the participation password remain locked after START, including during PAUSED. The administrator can still update the edition name/description, rename participants, or exclude a participant. Exclusion revokes participant sessions and removes that participant from rankings while preserving their historical answers. Finished results cannot be changed through participant management.

The admin dashboard includes competition status, edition and participant counts, and a quick link to active live controls. The live panel includes an admin-only leaderboard that updates after each answer. Ordinary users cannot read this live-score endpoint or answer keys before publication.

Submitted answers are final. Exact correct selections earn one point; wrong, missing, or partial selections earn zero. There are no speed bonuses. Tied scores share the same competition rank (for example 1, 2, 2, 4).

Refresh and network reconnection preserve an existing participant's session and submitted answer. Guests need their original browser cookie; knowing another participant's name and the edition password cannot recover that person's session. A signed-in USER's participation is linked to their account and can be recovered after logging into that same account on another browser/device, including after START. This restores an existing enrollment and never creates a late enrollment. **Participările mele** lists account-linked sessions. Logging out blocks access to account-linked participation until the same account logs in again.

## Accounts and administrator assignment

- `/register`: name, email and password (minimum 12 characters), with confirmation in the UI. Successful registration signs in with role USER.
- `/login`: email and password for both roles. ADMIN opens the dashboard; USER returns to public contests.
- Navbar: account name, role-appropriate navigation and logout. The React admin route rejects USER accounts before mounting administrative content; the API independently checks the current database role on every request.
- Account cookies are HttpOnly, SameSite=Lax, Secure when configured for HTTPS, and backed by hashed opaque tokens in the database. Authenticated writes require the matching CSRF token. No credentials are stored in localStorage.
- Public registration rejects extra fields, including `role` and `username`. There is no public role-change endpoint. Only trusted server operators can create the first admin through environment configuration or promote an existing registered account through the CLI.

From `backend/`, with the same database environment variables as the API:

```sh
python -m app.manage list-admins
python -m app.manage promote participant@example.com
python -m app.manage set-email admin@example.com actual-admin@your-domain.com
```

In Docker, prefix these commands with `docker compose exec backend`. Promotion/email changes revoke that account's existing account sessions; the account must sign in again. An existing USER email is never silently promoted by the initial-admin bootstrap.

Public browsing and the original guest name/password participation remain available. Authenticated users additionally receive catalogue status updates through `/ws/catalog`, can restore their participations, and can view published final results even if they did not participate. Email verification, password-reset delivery and social sign-in are not implemented.

## Edition lifecycle

The existing Competition → Edition hierarchy is preserved. Each **edition** persists its own lifecycle; the parent competition's displayed status is aggregated from its editions, prioritizing LIVE, PAUSED, WAITING, SCHEDULED, DRAFT and FINISHED.

```mermaid
stateDiagram-v2
    DRAFT --> SCHEDULED: schedule date
    DRAFT --> WAITING: open registrations
    SCHEDULED --> WAITING: open registrations
    WAITING --> LIVE: manual START
    LIVE --> PAUSED: pause
    PAUSED --> LIVE: resume
    LIVE --> FINISHED: last-question finish / early stop
    PAUSED --> FINISHED: early stop
```

**SCHEDULED announces a date/time; opening registrations and starting remain manual.** There is no automatic timer or automatic start. The date is stored in UTC and displayed in the browser's local time zone. WAITING is retained as the registration stage to preserve the original quiz rules. New enrollments are blocked in LIVE, PAUSED and FINISHED. Start/finish and question progression use validated transactions; pause/resume/stop also require `expected_revision` so stale commands cannot affect a newer state.

## Data model and consistency

`Competition → Edition → Question → QuestionOption`

`Edition → Participant → ParticipantAnswer → AnswerSelection`

`Account` (ADMIN or USER) and `Participant` each have database-backed `AuthSession` records. A participant can optionally reference an account, with at most one participation per account/edition. Passwords use Argon2id. Session tokens are randomly generated and stored as SHA-256 hashes, with account and edition-specific participant cookies. `Admin` remains a Python model alias only for older server-side integrations; the database table is `accounts`.

- Database foreign keys and cascading deletions protect referential integrity.
- Unique constraints protect normalized participant names, question positions, and one answer per participant/question.
- UTC timestamps track creation, joining, answers, start, finish, and session expiration.
- All critical operations acquire the same edition row lock using `SELECT … FOR UPDATE`. Joining and START, answering and NEXT/pause/stop, participant exclusion and answering, and question editing and START serialize against that lock.
- START and FINISH are idempotent. NEXT requires `expected_question_id`; a repeated or stale command returns HTTP 409 and never skips an additional question.
- Final scores are persisted in the same transaction that marks the edition FINISHED. Leaderboards are deterministically derived from those persisted scores.
- LIVE and PAUSED editions and their parent competitions cannot be deleted. Other deletions require UI confirmation.

## API

The versioned API prefix is `/api/v1`. Interactive OpenAPI is at `/api/docs`.

| Routes | Access |
| --- | --- |
| `POST /auth/register`, `POST /auth/login`, `GET /auth/session`, `POST /auth/logout` | Email account lifecycle; public registration always USER |
| `GET /auth/participations` | Signed-in account's own participations |
| `POST /admin/login`, `GET /admin/session`, `POST /admin/logout` | Admin authentication/session lifecycle |
| `GET /admin/overview` | Admin dashboard counts |
| `GET/POST /competitions`, `GET/PATCH/DELETE /competitions/{id}` | Admin |
| `GET/POST /competitions/{id}/editions` | Admin |
| `GET/PATCH/DELETE /editions/{id}` | Admin |
| `GET/POST /editions/{id}/questions`, `PATCH/DELETE /questions/{id}` | Admin |
| `PUT /editions/{id}/questions/order` | Admin; complete question ID ordering |
| `POST /editions/{id}/open`, `/start`, `/next`, `/finish`, `/schedule`, `/pause`, `/resume`, `/stop` | Admin |
| `GET /editions/{id}/participants`, `/admin-state` | Admin |
| `PATCH/DELETE /editions/{id}/participants/{participant_id}` | Admin; rename, delete before START or exclude during LIVE/PAUSED |
| `GET /editions/{id}/live-results` | Admin only, including before final publication |
| `GET /public/editions`, `/public/editions/{id}` | Public metadata only |
| `POST /editions/{id}/join` | Name/password; new joins only while WAITING |
| `GET /editions/{id}/state` | Participant's edition or admin |
| `POST /editions/{id}/answers` | Participant in the matching edition |
| `GET /editions/{id}/results` | Matching guest participant or authenticated account, only after FINISHED and publication |
| `WS /ws/editions/{id}` | Authenticated session and allowed browser Origin |
| `WS /ws/catalog` | Signed-in account; public metadata invalidations only |

Authenticated writes require `X-CSRF-Token`, obtained from the session/state response. Cookies are HttpOnly and SameSite=Lax. Untrusted origins and cross-site writes are rejected. Same-origin deployment needs no cross-origin API grants. All admin endpoints check the admin role independently; participant endpoints check edition membership. Auth and join routes have bounded per-IP rate limits (15 admin attempts and 120 joins per minute, allowing shared participant networks). Validation errors do not echo passwords. No credentials or quiz state are stored in localStorage.

WebSocket messages include event, edition ID, and revision. Clients ignore duplicate edition revisions. `SYNC` always reloads the state. Events include `PARTICIPANT_JOINED`, `PARTICIPANT_UPDATED`, `PARTICIPANT_REMOVED`, `EDITION_SCHEDULED`, `EDITION_UPDATED`, `QUIZ_STARTED`, `QUIZ_PAUSED`, `QUIZ_RESUMED`, `QUESTION_CHANGED`, `ANSWER_SUBMITTED`, and `QUIZ_FINISHED`. Payloads contain invalidations only; each client then reads an authorized snapshot. Client text `ping` receives `PONG`; idle or expired sessions are disconnected.

## Database migrations

```sh
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

For a schema change, configure a development database, update SQLAlchemy models, then run from `backend/`:

```sh
alembic revision --autogenerate -m "Describe schema change"
alembic upgrade head
alembic check
```

Review generated migrations before applying them. Back up the database before production migrations. The initial migration has an explicit schema and a reversible enum cleanup.

## Testing

Backend tests require a **separate PostgreSQL database named `quiz_test`** or a SQLite file whose name ends in `quiz_test.sqlite3`. They refuse to run without an explicit `TEST_DATABASE_URL` matching one of these test database names. **All test data in that database is erased between tests.** They never use an in-memory database. For SQLite, set `TEST_DATABASE_URL=sqlite:///C:/path/to/quiz_test.sqlite3`; the tests create its schema automatically.

```powershell
# Create quiz_test with your PostgreSQL tools first.
$env:TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/quiz_test'
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

```sh
cd frontend
npm ci
npm test
npm run build
npm audit
```

The browser acceptance test uses the running application and real database, with one admin and three separate participant browser contexts. It creates five questions in the UI (including multiple-choice), opens registration, joins participants, starts, blocks a late join, submits answers, advances each question, reloads sessions, disconnects/reconnects a participant, and checks final scores and shared ranks. Test-created competitions are removed afterward. Do not run this test against an event currently in use.

```powershell
cd frontend
# Supply the real initial credentials without putting them in test source.
$env:E2E_ADMIN_EMAIL='admin@example.com'
$env:E2E_ADMIN_PASSWORD='<your admin password>'
$env:E2E_BASE_URL='http://localhost:5173' # use :8080 for Compose
$env:E2E_BROWSER_CHANNEL='chrome'       # use installed Chrome, or omit after installing Playwright Chromium
npm run test:e2e
```

If a browser is not installed, run `npx playwright install chromium` and omit `E2E_BROWSER_CHANNEL`. Screenshots and failure traces are written to ignored `frontend/test-results/`.

The additional account/control browser test registers a USER through the UI, checks that admin navigation/API access is denied, observes SCHEDULED → WAITING without refresh, participates, pauses/resumes, verifies disabled answering while paused, restores the same account after logout/login, and stops early with persisted scoring. Test competitions are removed afterward; generated `e2e-user-…@example.com` accounts remain in the development database. Use a dedicated development instance for browser tests.

## Runtime limits

This version intentionally uses **one FastAPI worker and one backend replica**. The WebSocket room registry and rate limiter are process-local; all durable competition/session/answer data lives in the configured SQLite or PostgreSQL database. Do not add workers or replicas without adding shared event delivery (for example PostgreSQL LISTEN/NOTIFY or Redis) and a shared rate limiter. No Redis service is required for this deployment.

If a backend restart happens between a database commit and its event broadcast, sockets reconnect and reload the committed state. An event is a notification, not the durable source of truth. Restarting a live edition never reopens registrations or resets the active question.

## Project layout

```text
backend/
  app/          configuration, models, schemas, security, services, API, realtime
  alembic/      explicit versioned database migration
  tests/        SQLite/PostgreSQL integration, authorization and concurrency tests
frontend/
  src/          React pages, reusable forms/components, API and reconnect hook
  e2e/          browser acceptance test
  nginx.conf    production REST/WebSocket proxy and SPA fallback
scripts/        Windows configuration/start/stop helpers
docker-compose.yml
.env.example
```

See [VALIDATION.md](VALIDATION.md) for the checks actually executed in the implementation environment.
