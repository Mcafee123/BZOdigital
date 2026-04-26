from typing import Optional, List
from datetime import datetime
from sqlmodel import Field, SQLModel, create_engine, Session, select
import json

class CrawledCity(SQLModel, table=True):
    city_name: str = Field(primary_key=True)
    pdf_urls_json: str
    last_crawled: datetime = Field(default_factory=datetime.utcnow)

sqlite_file_name = "bzo_cache.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

def save_crawled_city(session: Session, city_name: str, pdf_urls: List[str]):
    city_name = city_name.lower()
    statement = select(CrawledCity).where(CrawledCity.city_name == city_name)
    existing_city = session.exec(statement).first()
    
    if existing_city:
        existing_city.pdf_urls_json = json.dumps(pdf_urls)
        existing_city.last_crawled = datetime.utcnow()
        session.add(existing_city)
    else:
        new_city = CrawledCity(
            city_name=city_name,
            pdf_urls_json=json.dumps(pdf_urls),
            last_crawled=datetime.utcnow()
        )
        session.add(new_city)
    session.commit()

def get_cached_city(session: Session, city_name: str) -> Optional[CrawledCity]:
    city_name = city_name.lower()
    statement = select(CrawledCity).where(CrawledCity.city_name == city_name)
    return session.exec(statement).first()

def clear_all_cache(session: Session):
    from sqlmodel import delete
    statement = delete(CrawledCity)
    session.exec(statement)
    session.commit()

