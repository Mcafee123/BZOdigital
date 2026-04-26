"""SQLite database layer using SQLModel."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bzo.db"

engine = None


def get_engine():
    global engine
    if engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    return engine


# --- Models ---


class BfsMunicipality(SQLModel, table=True):
    bfs_nr: int = Field(primary_key=True)
    name: str = Field(index=True)
    canton: str = Field(index=True)


class CantonGemeinde(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    canton: str = Field(index=True)
    name: str
    url: str
    last_scraped: datetime = Field(default_factory=datetime.utcnow)


class SearchCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cache_key: str = Field(unique=True, index=True)
    results_json: str
    last_searched: datetime = Field(default_factory=datetime.utcnow)


# --- DB init ---


def init_db():
    """Create tables if they don't exist."""
    SQLModel.metadata.create_all(get_engine())


def get_session():
    """Get a new session. Use as context manager or FastAPI dependency."""
    return Session(get_engine())


# --- BFS operations ---


def load_bfs_from_db() -> list[dict]:
    """Load all BFS municipalities from DB."""
    with get_session() as session:
        results = session.exec(select(BfsMunicipality)).all()
        return [{"bfs_nr": m.bfs_nr, "name": m.name, "canton": m.canton} for m in results]


def save_bfs_to_db(municipalities: list[dict]):
    """Replace all BFS data in DB."""
    with get_session() as session:
        session.exec(select(BfsMunicipality)).all()  # load
        # Delete all existing
        for m in session.exec(select(BfsMunicipality)).all():
            session.delete(m)
        # Insert new
        for m in municipalities:
            session.add(BfsMunicipality(**m))
        session.commit()


# --- Canton operations ---


def load_canton_from_db(canton_id: str) -> list[dict[str, str]] | None:
    """Load canton Gemeinde mapping from DB."""
    with get_session() as session:
        results = session.exec(
            select(CantonGemeinde).where(CantonGemeinde.canton == canton_id)
        ).all()
        if not results:
            return None
        return [{"name": g.name, "url": g.url} for g in results]


def save_canton_to_db(canton_id: str, data: list[dict[str, str]]):
    """Replace canton Gemeinde mapping in DB."""
    with get_session() as session:
        # Delete existing for this canton
        existing = session.exec(
            select(CantonGemeinde).where(CantonGemeinde.canton == canton_id)
        ).all()
        for g in existing:
            session.delete(g)
        # Insert new
        now = datetime.utcnow()
        for g in data:
            session.add(CantonGemeinde(canton=canton_id, name=g["name"], url=g["url"], last_scraped=now))
        session.commit()


# --- Search cache operations ---


def get_cached_search(cache_key: str, max_age: timedelta = timedelta(hours=24)) -> list[dict] | None:
    """Get cached search results if fresh enough."""
    with get_session() as session:
        result = session.exec(
            select(SearchCache).where(SearchCache.cache_key == cache_key)
        ).first()
        if result and datetime.utcnow() - result.last_searched < max_age:
            return json.loads(result.results_json)
        return None


def save_search_cache(cache_key: str, results: list[dict]):
    """Save or update search results in cache."""
    with get_session() as session:
        existing = session.exec(
            select(SearchCache).where(SearchCache.cache_key == cache_key)
        ).first()
        if existing:
            existing.results_json = json.dumps(results)
            existing.last_searched = datetime.utcnow()
            session.add(existing)
        else:
            session.add(SearchCache(
                cache_key=cache_key,
                results_json=json.dumps(results),
                last_searched=datetime.utcnow(),
            ))
        session.commit()


def clear_search_cache():
    """Clear all search cache entries."""
    with get_session() as session:
        for entry in session.exec(select(SearchCache)).all():
            session.delete(entry)
        session.commit()


