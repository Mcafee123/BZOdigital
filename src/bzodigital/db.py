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


class Label(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class PdfAnnotation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    municipality_bfs_nr: int = Field(index=True)
    pdf_url: str
    pdf_title: str = ""
    labels_json: str = "[]"
    selected: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


DEFAULT_LABELS = [
    "Synopse",
    "Bau- und Zonenordnung alt",
    "Bau- und Zonenordnung neu",
    "Einwendungsbericht gemäss § 7 PBG",
    "Erläuterungsbericht gemäss Art. 47 RPV",
    "Gemeindeversammlungsbeschluss",
]


# --- DB init ---


def init_db():
    """Create tables if they don't exist, seed default labels."""
    SQLModel.metadata.create_all(get_engine())
    _seed_default_labels()


def _seed_default_labels():
    """Insert default labels if they don't exist yet."""
    with get_session() as session:
        existing = {l.name for l in session.exec(select(Label)).all()}
        for name in DEFAULT_LABELS:
            if name not in existing:
                session.add(Label(name=name))
        session.commit()


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


# --- Label operations ---


def get_labels() -> list[str]:
    """Get all label names."""
    with get_session() as session:
        return [l.name for l in session.exec(select(Label)).all()]


def add_label(name: str) -> str:
    """Add a new label. Returns the name. Raises ValueError if duplicate."""
    with get_session() as session:
        existing = session.exec(select(Label).where(Label.name == name)).first()
        if existing:
            raise ValueError(f"Label '{name}' already exists.")
        session.add(Label(name=name))
        session.commit()
    return name


# --- Annotation operations ---


def get_annotations(bfs_nr: int) -> list[dict]:
    """Get all annotations for a municipality."""
    with get_session() as session:
        results = session.exec(
            select(PdfAnnotation).where(PdfAnnotation.municipality_bfs_nr == bfs_nr)
        ).all()
        return [
            {
                "id": a.id,
                "municipality_bfs_nr": a.municipality_bfs_nr,
                "pdf_url": a.pdf_url,
                "pdf_title": a.pdf_title,
                "labels": json.loads(a.labels_json),
                "selected": a.selected,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
            }
            for a in results
        ]


def upsert_annotation(
    bfs_nr: int,
    pdf_url: str,
    pdf_title: str,
    labels: list[str],
    selected: bool,
    *,
    skip_if_labeled: bool = False,
) -> dict:
    """Create or update an annotation for a PDF. Keyed by (bfs_nr, pdf_url).

    When skip_if_labeled is True and the existing row already has labels,
    leave the row untouched (used by auto-classification to avoid stomping
    user edits).
    """
    with get_session() as session:
        existing = session.exec(
            select(PdfAnnotation).where(
                PdfAnnotation.municipality_bfs_nr == bfs_nr,
                PdfAnnotation.pdf_url == pdf_url,
            )
        ).first()

        if existing and skip_if_labeled and json.loads(existing.labels_json or "[]"):
            return {
                "id": existing.id,
                "municipality_bfs_nr": existing.municipality_bfs_nr,
                "pdf_url": existing.pdf_url,
                "pdf_title": existing.pdf_title,
                "labels": json.loads(existing.labels_json),
                "selected": existing.selected,
                "created_at": existing.created_at.isoformat(),
                "updated_at": existing.updated_at.isoformat(),
            }

        now = datetime.utcnow()
        if existing:
            existing.pdf_title = pdf_title
            existing.labels_json = json.dumps(labels)
            existing.selected = selected
            existing.updated_at = now
            session.add(existing)
            session.commit()
            session.refresh(existing)
            ann = existing
        else:
            ann = PdfAnnotation(
                municipality_bfs_nr=bfs_nr,
                pdf_url=pdf_url,
                pdf_title=pdf_title,
                labels_json=json.dumps(labels),
                selected=selected,
                created_at=now,
                updated_at=now,
            )
            session.add(ann)
            session.commit()
            session.refresh(ann)

        return {
            "id": ann.id,
            "municipality_bfs_nr": ann.municipality_bfs_nr,
            "pdf_url": ann.pdf_url,
            "pdf_title": ann.pdf_title,
            "labels": json.loads(ann.labels_json),
            "selected": ann.selected,
            "created_at": ann.created_at.isoformat(),
            "updated_at": ann.updated_at.isoformat(),
        }


def delete_annotation(annotation_id: int):
    """Delete an annotation by ID."""
    with get_session() as session:
        ann = session.exec(
            select(PdfAnnotation).where(PdfAnnotation.id == annotation_id)
        ).first()
        if ann:
            session.delete(ann)
            session.commit()
