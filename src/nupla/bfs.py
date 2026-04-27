"""BFS (Federal Statistical Office) municipality register."""

import json
from dataclasses import dataclass
from pathlib import Path

from thefuzz import fuzz, process

from nupla.db import init_db, load_bfs_from_db, save_bfs_to_db

BFS_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bfs_municipalities.json"
BFS_DOWNLOAD_URL = "https://dam-api.bfs.admin.ch/hub/api/dam/assets/286080/master"


@dataclass(frozen=True)
class Municipality:
    bfs_nr: int
    name: str
    canton: str


def load_bfs() -> list[Municipality]:
    """Load BFS municipality register from DB (initializes and seeds if needed)."""
    init_db()
    data = load_bfs_from_db()
    return [Municipality(**m) for m in data]


def fuzzy_find_municipality(
    query: str, municipalities: list[Municipality], limit: int = 5
) -> list[tuple[Municipality, int]]:
    """Fuzzy-match query against BFS municipality names."""
    names = [m.name for m in municipalities]
    results = process.extract(query, names, scorer=fuzz.WRatio, limit=limit)

    matches = []
    for name, score, *_ in results:
        muni = next(m for m in municipalities if m.name == name)
        matches.append((muni, score))
    return matches


async def update_bfs_register() -> Path:
    """Download latest BFS register, save to DB and JSON."""
    import tempfile

    import httpx
    import xlrd

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.get(BFS_DOWNLOAD_URL)
        resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as f:
        f.write(resp.content)
        tmp = f.name

    try:
        wb = xlrd.open_workbook(tmp)
        ws = wb.sheet_by_name("Gemeindeliste-Liste d. communes")

        municipalities: list[dict] = []
        seen: set[int] = set()

        for r in range(1, ws.nrows):
            canton = ws.cell_value(r, 0)
            bfs_nr = int(ws.cell_value(r, 2))
            name = ws.cell_value(r, 3)
            if canton and name and bfs_nr not in seen:
                seen.add(bfs_nr)
                municipalities.append({"bfs_nr": bfs_nr, "name": name, "canton": canton})
    finally:
        Path(tmp).unlink(missing_ok=True)

    # Save to JSON (for seeding / git)
    BFS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    BFS_JSON_PATH.write_text(json.dumps(municipalities, indent=2, ensure_ascii=False))

    # Save to DB
    init_db()
    save_bfs_to_db(municipalities)

    return BFS_JSON_PATH
