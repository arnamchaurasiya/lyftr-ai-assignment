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
    seen = set()

    # Primary: landmark-based sections
    for tag in soup.find_all(["header", "main", "section", "article", "footer"]):
        section = build_section(tag, url, idx)
        if section:
            key = section["label"]
            if key not in seen:
                sections.append(section)
                seen.add(key)
                idx += 1

    # Fallback: heading-based grouping
    if not sections:
        for h in soup.find_all(["h1", "h2", "h3"]):
            parent = h.parent
            section = build_section(parent, url, idx)
            if section:
                key = section["label"]
                if key not in seen:
                    sections.append(section)
                    seen.add(key)
                    idx += 1

    # Final safety net
# Final safety: React / SPA content root
    if not sections:
        root = soup.find(id="__next") or soup.find("main") or soup.body
        if root:
            section = build_section(root, url, 0)
            if section:
                sections.append(section)


    return meta, sections


##adding this function
def follow_pagination(page, url, interactions, max_pages=3):
    for i in range(1, max_pages):
        try:
            next_link = page.query_selector(
                "a:has-text('More'), a:has-text('Next'), a:has-text('Older')"
            )
            if not next_link:
                break

            next_url = next_link.get_attribute("href")
            if not next_url:
                break

            absolute = next_url if next_url.startswith("http") else url + next_url
            page.goto(absolute, wait_until="domcontentloaded", timeout=30000)

            interactions["pages"].append(absolute)
        except:
            break


def find_next_page_static(soup, base_url):
    more = soup.find("a", string=lambda s: s and s.lower() in ["more", "next", "older"])
    if more and more.get("href"):
        return urljoin(base_url, more["href"])
    return None


def scrape(url: str):
    scraped_at = datetime.utcnow().isoformat() + "Z"
    interactions = {"clicks": [], "scrolls": 0, "pages": [url]}
    errors = []

    # ---- STATIC FIRST ----
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True)
        r.raise_for_status()
        meta = {}
        all_sections = []
        pages = [url]

        current_url = url

        for i in range(3):  # depth >= 3
            r = httpx.get(current_url, timeout=10, follow_redirects=True)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")
            meta, sections = parse_html(r.text, current_url)

            all_sections.extend(sections)

            next_url = find_next_page_static(soup, current_url)
            if not next_url:
                break

            pages.append(next_url)
            current_url = next_url

        interactions["pages"] = pages
        interactions["clicks"].append("pagination: More/Next")

        if all_sections:
            return {
                "result": {
                    "url": url,
                    "scrapedAt": scraped_at,
                    "meta": meta,
                    "sections": all_sections,
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

            # --- Scroll first ---
            initial_height = page.evaluate("document.body.scrollHeight")

            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)

                interactions["scrolls"] += 1
                interactions["clicks"].append("window.scrollTo(bottom)")

            final_height = page.evaluate("document.body.scrollHeight")

            # --- Pagination fallback ONLY if scroll didn't load content ---
            if final_height == initial_height:
                follow_pagination(page, url, interactions)

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
