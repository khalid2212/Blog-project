# My Blog — FastAPI + Vanilla JavaScript

A complete blog website served by **one FastAPI process on one domain/port**. No React, npm, frontend build process, or external CSS framework.

## Pages
- `/` — homepage / all posts
- `/post.html?id=1` — article view; author's Edit/Delete actions
- `/login.html` — login
- `/register.html` — registration
- `/editor.html` — write a post
- `/editor.html?id=1` — edit your post
- `/docs` — API docs

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```

Set a **stable strong secret** before deploying (do not use the example value):

Windows PowerShell:
```powershell
$env:BLOG_SECRET_KEY = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
python -m uvicorn blog.main:app --reload
```

Linux/macOS:
```bash
export BLOG_SECRET_KEY='REPLACE_WITH_A_LONG_RANDOM_SECRET'
python -m uvicorn blog.main:app --reload
```

Open http://127.0.0.1:8000

## Deploy on one server
Install `requirements.txt`, configure `BLOG_SECRET_KEY` as an environment variable, then start:

```bash
python -m uvicorn blog.main:app --host 0.0.0.0 --port 8000
```

Point your reverse proxy/domain at port 8000 and enable HTTPS. FastAPI serves both pages (`/`) and the API (`/api/`). Frontend fetch calls use relative URLs so there is no CORS setup or backend URL to edit when serving from the same origin.

`blog.db` will be created automatically in the project directory (or use `BLOG_DB_PATH` to choose a persistent disk path). **Back up this file** and use persistent storage with hosting. Do not commit or expose `blog.db` or your secret key. For multi-instance/large-scale deployment, move to PostgreSQL.

## API
| Method | URL | Authentication |
|---|---|---|
| POST | `/api/register` | Public |
| POST | `/api/login` | Public |
| GET | `/api/me` | Required |
| GET | `/api/posts` | Public |
| GET | `/api/posts/{id}` | Public |
| POST | `/api/posts` | Required |
| PUT | `/api/posts/{id}` | Owner only |
| DELETE | `/api/posts/{id}` | Owner only |

Authorization header: `Authorization: Bearer <access_token>`.

### Notes
- The frontend stores a token in **sessionStorage** for this educational example. This is not resistant to XSS; hardened production authentication may use secure HttpOnly cookies and CSRF protection. Always deploy over HTTPS.
- `BLOG_SECRET_KEY` is required for stable sessions across restarts. When omitted, the app generates an ephemeral key and prints a warning (development only).
- Newly created blog schema has `users` and `posts` with a foreign key. Older `blog.db` versions require a database migration rather than relying on CREATE TABLE IF NOT EXISTS.
- All user-provided text is inserted as text/HTML-escaped on the frontend; no HTML markup in post content is rendered.
- API endpoint prefix is `/api` so it never conflicts with HTML routes.
