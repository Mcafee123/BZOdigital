import argparse
from googlesearch import search
import time

def get_bzo_links(gemeinde_domain: str, max_results: int = 10):
    """
    Sucht via Google nach BZO-relevanten PDF-Dokumenten für eine spezifische Gemeinde.
    Nutzt Search Engine Dorking, um Dokumente zu finden, ohne die Seite selbst crawlen zu müssen.
    
    HINWEIS: Kostenlose Bibliotheken wie `googlesearch-python` werden von Google oft blockiert 
    (geben dann leere Resultate zurück). Für einen produktiven Einsatz empfiehlt sich 
    eine offizielle API wie SerpApi (https://serpapi.com/).
    """
    # Konstruiere den Dorking-Query
    query = f'site:{gemeinde_domain} filetype:pdf "Bau- und Zonenordnung" OR "BZO" OR "Zonenplan" OR "Bauordnung"'
    print(f"Suche nach: {query}\n")
    
    links = []
    try:
        # Die Google Search API gibt direkt die URLs als Strings zurück
        for url in search(query, num_results=max_results, sleep_interval=2):
            links.append(url)
                
        return links
    except Exception as e:
        print(f"Fehler bei der Suche: {e}")
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawlt BZO PDF-Links für eine Schweizer Gemeinde.")
    parser.add_argument("domain", help="Die Domain der Gemeinde, z.B. waedenswil.ch")
    parser.add_argument("--max", type=int, default=10, help="Maximale Anzahl an Resultaten (Standard: 10)")
    
    args = parser.parse_args()
    
    found_links = get_bzo_links(args.domain, args.max)
    
    if not found_links:
        print(f"Keine relevanten BZO-Dokumente für {args.domain} gefunden.")
    else:
        print("Gefundene PDF-Links:")
        for idx, link in enumerate(found_links, 1):
            print(f"[{idx}] {link}")
