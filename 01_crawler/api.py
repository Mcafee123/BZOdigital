from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import List
import json
import os
from datetime import datetime, timedelta

from sqlmodel import Session
from database import create_db_and_tables, get_session, save_crawled_city, get_cached_city, clear_all_cache
from crawler import crawl_for_bzo

app = FastAPI(
    title="BZO Digital Crawler API",
    description="REST API zum automatischen Crawlen und Cachen von Bau- und Zonenordnungen von Schweizer Gemeinden."
)

# Load the cities mapping
CITIES_FILE = "cities.json"

def load_cities():
    if not os.path.exists(CITIES_FILE):
        return {}
    with open(CITIES_FILE, "r") as f:
        return json.load(f)

# Pydantic models for request/response
class BatchRequest(BaseModel):
    cities: List[str]

class CrawlResponse(BaseModel):
    city: str
    source_url: str
    cached: bool
    last_crawled: datetime
    pdf_urls: List[str]

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

def background_crawl_task(cities: List[str]):
    """Background task to crawl multiple cities sequentially."""
    city_mapping = load_cities()
    
    # Needs a separate session since it's running in background
    from database import engine
    
    with Session(engine) as session:
        for city_name in cities:
            city_key = city_name.lower().strip()
            if city_key not in city_mapping:
                print(f"[Batch] Überspringe {city_key} (Nicht in cities.json gefunden)")
                continue
                
            start_url = city_mapping[city_key]
            
            # Check if it needs a refresh (older than 24h)
            cached = get_cached_city(session, city_key)
            if cached and datetime.utcnow() - cached.last_crawled < timedelta(days=1):
                print(f"[Batch] Überspringe {city_key} (Cache ist noch aktuell)")
                continue
                
            print(f"[Batch] Starte Crawl für {city_key}...")
            try:
                # Assuming max_pages=100 as default
                found_pdfs = crawl_for_bzo(start_url, max_pages=1500)
                save_crawled_city(session, city_key, found_pdfs)
                print(f"[Batch] {city_key} abgeschlossen. {len(found_pdfs)} PDFs gefunden.")
            except Exception as e:
                print(f"[Batch] Fehler beim Crawlen von {city_key}: {e}")

@app.get("/api/bzo/{city_name}", response_model=CrawlResponse)
def get_city_bzo(city_name: str, session: Session = Depends(get_session)):
    """
    Holt die BZO-PDFs für eine gegebene Stadt. 
    Nutzt den Cache, falls die Daten weniger als 24 Stunden alt sind.
    Andernfalls wird synchron gecrawlt (kann ca. 1 Minute dauern).
    """
    city_key = city_name.lower().strip()
    city_mapping = load_cities()
    
    if city_key not in city_mapping:
        raise HTTPException(status_code=404, detail=f"Stadt '{city_name}' nicht in Konfiguration (cities.json) gefunden.")
        
    start_url = city_mapping[city_key]
    
    # Check Database Cache
    cached_city = get_cached_city(session, city_key)
    
    if cached_city:
        age = datetime.utcnow() - cached_city.last_crawled
        if age < timedelta(days=1):
            # Cache is fresh
            return CrawlResponse(
                city=city_name,
                source_url=start_url,
                cached=True,
                last_crawled=cached_city.last_crawled,
                pdf_urls=json.loads(cached_city.pdf_urls_json)
            )
            
    # Cache is missing or expired -> Start synchronous crawl
    print(f"[API] Starte Live-Crawl für {city_name} (Cache ungültig oder nicht vorhanden)...")
    try:
        found_pdfs = crawl_for_bzo(start_url, max_pages=1500)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Crawlen: {str(e)}")
        
    # Save to Cache
    save_crawled_city(session, city_key, found_pdfs)
    
    # Re-fetch from cache to get accurate timestamps
    updated_city = get_cached_city(session, city_key)
    
    return CrawlResponse(
        city=city_name,
        source_url=start_url,
        cached=False,
        last_crawled=updated_city.last_crawled,
        pdf_urls=json.loads(updated_city.pdf_urls_json)
    )

@app.post("/api/bzo/batch")
def batch_crawl(request: BatchRequest, background_tasks: BackgroundTasks):
    """
    Nimmt eine Liste von Städten entgegen und startet das Crawlen asynchron im Hintergrund.
    Ideal, um den Cache vorab für Demos zu füllen.
    """
    background_tasks.add_task(background_crawl_task, request.cities)
    
    return {
        "message": f"Crawling für {len(request.cities)} Städte im Hintergrund gestartet.",
        "cities": request.cities
    }

@app.delete("/api/bzo/cache")
def delete_cache(session: Session = Depends(get_session)):
    """
    Löscht den gesamten Cache für alle Städte.
    """
    try:
        clear_all_cache(session)
        return {"message": "Cache wurde erfolgreich gelöscht."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen des Caches: {str(e)}")

def start():
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start()
