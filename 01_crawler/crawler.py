import argparse
import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import xml.etree.ElementTree as ET
import re

KEYWORDS = ["bzo", "bau- und zonenordnung", "bauordnung", "zonenplan", "zonenordnung", "zonenreglement"]
# Keywords, um vielversprechende HTML-Seiten in der Sitemap oder beim Crawlen zu identifizieren
SITEMAP_TARGET_KEYWORDS = ["bau", "zonen", "bzo", "reglement", "publikation", "raumplanung", "amt", "verwaltung"]

def is_valid_internal_url(url, base_domain):
    """Prüft, ob die URL zur gleichen Domain gehört und ob es wahrscheinlich eine HTML-Seite ist."""
    try:
        parsed = urlparse(url)
        if base_domain not in parsed.netloc:
            return False
            
        ignored_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.zip', '.doc', '.docx', '.xls', '.xlsx', '.mp4', '.pdf']
        if any(parsed.path.lower().endswith(ext) for ext in ignored_extensions):
            return False
            
        return True
    except:
        return False

def contains_keywords(text):
    """Prüft ob der Text (URL oder Link-Text) BZO-relevante Keywords enthält."""
    text = text.lower()
    return any(kw in text for kw in KEYWORDS)

def scan_page_for_pdfs(url, session, found_pdfs):
    """Lädt eine HTML-Seite herunter und sucht nach PDFs mit passenden Keywords."""
    try:
        response = session.get(url, timeout=5)
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            link_text = a_tag.get_text().strip()
            absolute_url = urljoin(url, href).split('#')[0]
            
            is_pdf = absolute_url.lower().endswith('.pdf') or 'download' in absolute_url.lower() or 'pdf' in absolute_url.lower()
            if is_pdf and (contains_keywords(absolute_url) or contains_keywords(link_text)):
                found_pdfs.add(absolute_url)
    except Exception:
        pass

def crawl_via_sitemap(start_url, session):
    """Versucht die Sitemap.xml herunterzuladen und gezielt Seiten zu scannen."""
    if not start_url.endswith('/'):
        start_url += '/'
    
    sitemap_url = urljoin(start_url, 'sitemap.xml')
    print(f"Versuche Option A: Suche nach Sitemap ({sitemap_url})...")
    
    try:
        response = session.get(sitemap_url, timeout=5)
        # Manche Server senden XML als text/html, daher prüfen wir beides (Status und Text)
        if response.status_code != 200 or '<urlset' not in response.text:
            print("Keine gültige Sitemap gefunden.")
            return None
            
        print("Sitemap gefunden! Analysiere URLs...")
        # XML parsen (Namespaces entfernen für einfache Suche)
        content = re.sub(r'\sxmlns="[^"]+"', '', response.text, count=1)
        root = ET.fromstring(content)
        
        urls_to_scan = []
        found_pdfs = set()
        
        for loc in root.findall('.//loc'):
            url = loc.text
            if not url: continue
            
            # Falls die Sitemap direkt ein PDF listet
            if url.lower().endswith('.pdf'):
                if contains_keywords(url):
                    found_pdfs.add(url)
            else:
                # Prüfen, ob die URL vielversprechend klingt (z.B. /verwaltung/bauamt)
                url_lower = url.lower()
                if any(kw in url_lower for kw in SITEMAP_TARGET_KEYWORDS):
                    urls_to_scan.append(url)
                    
        print(f"{len(urls_to_scan)} vielversprechende Unterseiten in der Sitemap gefunden. Scanne diese...")
        
        # Scanne nur die vielversprechenden Seiten
        for idx, url in enumerate(urls_to_scan, 1):
            print(f"[Sitemap {idx}/{len(urls_to_scan)}] Scanne: {url}")
            scan_page_for_pdfs(url, session, found_pdfs)
            
        return found_pdfs
        
    except Exception as e:
        print(f"Fehler beim Sitemap-Parsing: {e}")
        return None

def crawl_for_bzo(start_url, max_pages=100):
    if not start_url.startswith('http'):
        start_url = 'https://' + start_url

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    })

    # 1. VERSUCH: SITEMAP (Sehr schnell)
    sitemap_pdfs = crawl_via_sitemap(start_url, session)
    
    if sitemap_pdfs is not None and len(sitemap_pdfs) > 0:
        print("\nErfolgreich via Sitemap gefunden!")
        return list(sitemap_pdfs)
        
    if sitemap_pdfs is not None and len(sitemap_pdfs) == 0:
        print("Sitemap erfolgreich gescannt, aber keine BZO-PDFs gefunden.")
        
    print("\nOption B: Starte Fallback (Heuristischer, rekursiver Crawler)...")
    
    # 2. VERSUCH: REKURSIVER CRAWLER (FALLBACK)
    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc.replace('www.', '')

    visited = set()
    queue = deque([start_url])
    found_pdfs = set()

    pages_crawled = 0

    while queue and pages_crawled < max_pages:
        current_url = queue.popleft()
        current_url = current_url.split('#')[0]

        if current_url in visited:
            continue
            
        visited.add(current_url)
        pages_crawled += 1
        
        print(f"[Fallback {pages_crawled}/{max_pages}] Scanne: {current_url}")

        try:
            response = session.get(current_url, timeout=5)
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'application/pdf' in content_type:
                if contains_keywords(current_url):
                    found_pdfs.add(current_url)
                continue
                
            if 'text/html' not in content_type:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                link_text = a_tag.get_text().strip()
                
                absolute_url = urljoin(current_url, href).split('#')[0]
                
                is_pdf = absolute_url.lower().endswith('.pdf') or 'download' in absolute_url.lower() or 'pdf' in absolute_url.lower()
                
                if is_pdf:
                    if contains_keywords(absolute_url) or contains_keywords(link_text):
                        found_pdfs.add(absolute_url)
                else:
                    if is_valid_internal_url(absolute_url, base_domain) and absolute_url not in visited and absolute_url not in queue:
                        # HEURISTIK FÜR FALLBACK: Priorisiere vielversprechende Links (Bauamt etc.)
                        # Wir fügen sie am Anfang der Liste ein (LIFO), damit sie sofort als nächstes gescannt werden!
                        if any(kw in absolute_url.lower() for kw in SITEMAP_TARGET_KEYWORDS):
                            queue.appendleft(absolute_url) 
                        else:
                            queue.append(absolute_url)
                        
        except Exception:
            pass

    return list(found_pdfs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schneller & Rekursiver BZO Crawler für Schweizer Gemeinden")
    parser.add_argument("domain", help="Start-URL oder Domain (z.B. adliswil.ch)")
    parser.add_argument("--max", type=int, default=100, help="Maximale Anzahl zu scannender Seiten im Fallback (Standard: 100)")
    
    args = parser.parse_args()
    
    start_time = time.time()
    pdfs = crawl_for_bzo(args.domain, args.max)
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    if not pdfs:
        print(f"Keine relevanten BZO-PDFs gefunden.")
        print("Tipp: Erhöhe ggf. das --max Limit für den Fallback-Crawler.")
    else:
        print(f"{len(pdfs)} relevante BZO-Dokumente gefunden:")
        for idx, pdf in enumerate(pdfs, 1):
            print(f"[{idx}] {pdf}")
            
    print("-" * 60)
    print(f"Zeit benötigt: {duration:.2f} Sekunden")
    print("="*60 + "\n")
