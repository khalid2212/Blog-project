"""Blog API and HTML frontend served from one FastAPI application."""
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
DB_PATH = Path(os.environ.get("BLOG_DB_PATH", str(ROOT / "blog.db")))
SECRET_KEY = os.environ.get("BLOG_SECRET_KEY")
if not SECRET_KEY:
    # Development convenience only: new key on every restart invalidates old sessions.
    SECRET_KEY = secrets.token_urlsafe(48)
    print("WARNING: BLOG_SECRET_KEY unset; using temporary key. Set it for deployment.")
ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()
security = HTTPBearer(auto_error=False)
app = FastAPI(title="My Blog API", version="1.0.0")


@contextmanager
def database():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)")


init_db()


class RegisterData(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginData(BaseModel):
    email: EmailStr
    password: str


class PostData(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(min_length=1, max_length=20000)


def public_post(row):
    return dict(row)


def create_token(user_id: int) -> str:
    return jwt.encode({
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
        "iat": datetime.now(timezone.utc),
    }, SECRET_KEY, algorithm=ALGORITHM)


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Please login first", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    with database() as db:
        user = db.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return dict(user)


@app.post("/api/register", status_code=201)
def register(data: RegisterData):
    email = str(data.email).strip().lower()
    with database() as db:
        try:
            db.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                       (data.name.strip(), email, password_hash.hash(data.password)))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email already exists")
    return {"message": "User registered successfully"}


@app.post("/api/login")
def login(data: LoginData):
    with database() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (str(data.email).strip().lower(),)).fetchone()
    if user is None or not password_hash.verify(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return {"access_token": create_token(user["id"]), "token_type": "bearer", "user": {
        "id": user["id"], "name": user["name"], "email": user["email"]}}


@app.get("/api/me")
def me(user: Annotated[dict, Depends(current_user)]):
    return user


POST_QUERY = """SELECT posts.id, posts.title, posts.content, posts.user_id,
                      posts.created_at, posts.updated_at, users.name AS author_name
                FROM posts JOIN users ON users.id = posts.user_id"""


@app.get("/api/posts")
def get_posts():
    with database() as db:
        rows = db.execute(POST_QUERY + " ORDER BY posts.id DESC").fetchall()
    return [public_post(r) for r in rows]


@app.get("/api/posts/{post_id}")
def get_post(post_id: int):
    with database() as db:
        post = db.execute(POST_QUERY + " WHERE posts.id = ?", (post_id,)).fetchone()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return public_post(post)


@app.post("/api/posts", status_code=201)
def create_post(data: PostData, user: Annotated[dict, Depends(current_user)]):
    with database() as db:
        cursor = db.execute("INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)",
                            (data.title.strip(), data.content.strip(), user["id"]))
        post_id = cursor.lastrowid
    return {"message": "Post created", "id": post_id}


def enforce_owner(db, post_id, user_id):
    post = db.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only edit or delete your own posts")


@app.put("/api/posts/{post_id}")
def update_post(post_id: int, data: PostData, user: Annotated[dict, Depends(current_user)]):
    with database() as db:
        enforce_owner(db, post_id, user["id"])
        cur = db.execute("""UPDATE posts SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ? AND user_id = ?""",
                         (data.title.strip(), data.content.strip(), post_id, user["id"]))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post updated successfully"}


@app.delete("/api/posts/{post_id}")
def delete_post(post_id: int, user: Annotated[dict, Depends(current_user)]):
    with database() as db:
        enforce_owner(db, post_id, user["id"])
        cur = db.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user["id"]))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted successfully"}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/{page}.html", include_in_schema=False)
def serve_page(page: str):
    if page not in {"index", "post", "login", "register", "editor"}:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(STATIC / f"{page}.html")
