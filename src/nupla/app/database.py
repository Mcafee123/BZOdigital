"""Database connection and models for the nupla-app backend."""
from sqlmodel import Field, Session, SQLModel, create_engine

from nupla.shared.paths import get_db_path

DB_PATH = get_db_path()

# Open as immutable read-only so a WAL-mode DB on a read-only mount (Azure Files
# in prod) doesn't try to create -shm/-wal sidecars and fail with SQLITE_CANTOPEN.
sqlite_url = f"sqlite:///file:{DB_PATH}?immutable=1&mode=ro&uri=true"

engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False, "uri": True},
)

def get_session():
    """Dependency for getting a database session."""
    with Session(engine) as session:
        yield session

# --- Models (Read-only views of the existing tables) ---

class BfsMunicipality(SQLModel, table=True):
    __tablename__ = "bfsmunicipality"

    bfs_nr: int = Field(primary_key=True)
    name: str
    canton: str

class PdfAnnotation(SQLModel, table=True):
    __tablename__ = "pdfannotation"

    id: int = Field(primary_key=True)
    municipality_bfs_nr: int
    pdf_url: str
    pdf_title: str
    labels_json: str
    selected: bool

