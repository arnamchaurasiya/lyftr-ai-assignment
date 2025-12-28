import httpx
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from playwright.sync_api import sync_playwright


def extract_meta(soup, url):
    title = soup.title.string.strip() if soup.title else ""
    desc = soup.find("meta", attrs={"name": "description"})
    lang = soup.html.get("lang") if soup.html else "en"
    canon = soup.find("link", rel="canonical")

    return {
        "title": title,
        "description": desc["content"] if desc else "",
        "language": lang or "en",
        "canonical": canon["href"] if canon else None,
    }


def build_section(tag, url, idx):
    text = tag.get_text(" ", strip=True)
    if not text:
        return None

    headings = [h.get_text(strip=True) for h in tag.find_all(["h1", "h2", "h3"])]

    links = [
        {"text": a.get_text(strip=True), "href": urljoin(url, a.get("href"))}
        for a in tag.find_all("a", href=True)
        if a.get_text(strip=True)
    ]

    images = [
        {"src": urljoin(url, img.get("src")), "alt": img.get("alt", "")}
        for img in tag.find_all("img", src=True)
    ]

    lists = [
        [li.get_text(strip=True) for li in ul.find_all("li")]
        for ul in tag.find_all(["ul", "ol"])
    ]

    label = headings[0] if headings else " ".join(text.split()[:6])

    return {
        "id": f"section-{idx}",
        "type": "section",
        "label": label,
        "sourceUrl": url,
        "content": {
            "headings": headings,
            "text": text[:3000],
            "links": links,
            "images": images,
            "lists": lists,
            "tables": [],
        },
        "rawHtml": str(tag)[:1500],
        "truncated": len(str(tag)) > 1500,
    }


def parse_html(html, url):
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_meta(soup, url)

    sections = []
    idx = 0

    for tag in soup.find_all(["header", "main", "section", "article", "footer"]):
        section = build_section(tag, url, idx)
        if section:
            sections.append(section)
            idx += 1

    # Fallback safety
    if not sections and soup.body:
        section = build_section(soup.body, url, 0)
        if section:
            sections.append(section)

    return meta, sections


def scrape(url: str):
    scraped_at = datetime.utcnow().isoformat() + "Z"
    interactions = {"clicks": [], "scrolls": 0, "pages": [url]}
    errors = []

    # ---- STATIC FIRST ----
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
        r.raise_for_status()
        meta, sections = parse_html(r.text, url)

        if sections and len(sections[0]["content"]["text"]) > 500:
            return {
                "result": {
                    "url": url,
                    "scrapedAt": scraped_at,
                    "meta": meta,
                    "sections": sections,
                    "interactions": interactions,
                    "errors": errors,
                }
            }
    except Exception as e:
        errors.append({"message": str(e), "phase": "static"})

    # ---- JS FALLBACK ----
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_load_state("networkidle", timeout=5000)
                interactions["scrolls"] += 1
                interactions["clicks"].append("window.scrollTo(bottom)")

            html = page.content()
            meta, sections = parse_html(html, url)
            browser.close()

            return {
                "result": {
                    "url": url,
                    "scrapedAt": scraped_at,
                    "meta": meta,
                    "sections": sections,
                    "interactions": interactions,
                    "errors": errors,
                }
            }
    except Exception as e:
        errors.append({"message": str(e), "phase": "js"})

    return {
        "result": {
            "url": url,
            "scrapedAt": scraped_at,
            "meta": {},
            "sections": [],
            "interactions": interactions,
            "errors": errors,
        }
    }
