import httpx
import time
from bs4 import BeautifulSoup, Tag, NavigableString
from urllib.parse import urljoin
from datetime import datetime
from playwright.sync_api import sync_playwright

# 1. HEADERS to avoid 403 blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def extract_meta(soup, url):
    title = soup.title.string.strip() if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = desc_tag["content"] if desc_tag else ""
    
    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else "en"
    
    canon_tag = soup.find("link", rel="canonical")
    canon = canon_tag["href"] if canon_tag else None

    return {
        "title": title,
        "description": desc,
        "language": lang or "en",
        "canonical": canon,
    }

def build_section_from_elements(elements, url, idx, label="Section"):
    text_parts = []
    links = []
    images = []
    lists = []
    headings = []

    for el in elements:
        if isinstance(el, NavigableString):
            txt = str(el).strip()
            if txt: text_parts.append(txt)
            continue
        
        if not isinstance(el, Tag):
            continue

        txt = el.get_text(" ", strip=True)
        if txt: text_parts.append(txt)

        if el.name in ["h1", "h2", "h3"]:
            headings.append(txt)
            for h in el.find_all(["h1", "h2", "h3"]):
                headings.append(h.get_text(strip=True))
        
        if el.name == "a" and el.get("href"):
             links.append({"text": txt, "href": urljoin(url, el.get("href"))})
        for a in el.find_all("a", href=True):
            links.append({"text": a.get_text(strip=True), "href": urljoin(url, a.get("href"))})

        if el.name == "img" and el.get("src"):
            images.append({"src": urljoin(url, el.get("src")), "alt": el.get("alt", "")})
        for img in el.find_all("img", src=True):
            images.append({"src": urljoin(url, img.get("src")), "alt": img.get("alt", "")})

        if el.name in ["ul", "ol"]:
            lists.append([li.get_text(strip=True) for li in el.find_all("li")])
        for ul in el.find_all(["ul", "ol"]):
             lists.append([li.get_text(strip=True) for li in ul.find_all("li")])

    full_text = " ".join(text_parts)
    if not full_text and not images:
        return None

    raw_html_snippet = "".join([str(e) for e in elements[:3]])[:1000]

    return {
        "id": f"section-{idx}",
        "type": "section",
        "label": label,
        "sourceUrl": url,
        "content": {
            "headings": headings,
            "text": full_text[:5000],
            "links": links,
            "images": images,
            "lists": lists,
            "tables": [],
        },
        "rawHtml": raw_html_snippet,
        "truncated": True,
    }

def parse_html(html, url):
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_meta(soup, url)
    sections = []
    idx = 0
    
    # Strategy 1: Explicit <section> tags
    explicit_sections = soup.find_all("section")
    if explicit_sections:
        for tag in explicit_sections:
            sec = build_section_from_elements([tag], url, idx)
            if sec:
                sections.append(sec)
                idx += 1
    
    # Strategy 2: Heading-based Partitioning
    if not sections:
        content_root = soup.find("main") or soup.find(id="content") or soup.find(id="bodyContent") or soup.body
        if content_root:
            current_elements = []
            current_label = "Introduction"
            
            for child in content_root.children:
                if isinstance(child, Tag) and child.name in ["h1", "h2", "h3"]:
                    if current_elements:
                        sec = build_section_from_elements(current_elements, url, idx, current_label)
                        if sec: 
                            sections.append(sec)
                            idx += 1
                    current_elements = []
                    current_label = child.get_text(strip=True) or "Section"
                    current_elements.append(child)
                else:
                    current_elements.append(child)
            
            if current_elements:
                sec = build_section_from_elements(current_elements, url, idx, current_label)
                if sec: sections.append(sec)

    return meta, sections

def find_next_page_static(soup, base_url):
    candidates = soup.find_all("a", href=True)
    for a in candidates:
        text = a.get_text(" ", strip=True).lower()
        if text in ["next", "more", "older posts", "next page", ">"]:
            return urljoin(base_url, a["href"])
        
        classes = a.get("class", [])
        if any("next" in c.lower() or "more" in c.lower() for c in classes):
            if len(text) < 20: 
                return urljoin(base_url, a["href"])
    return None

def scrape(url: str):
    scraped_at = datetime.utcnow().isoformat() + "Z"
    interactions = {"clicks": [], "scrolls": 0, "pages": [url]}
    errors = []
    
    # Store a robust static result in case JS fails
    backup_result = None

    # ---- STATIC ATTEMPT ----
    try:
        current_url = url
        all_sections = []
        visited_pages = [url]
        meta = {}

        for i in range(3): 
            r = httpx.get(current_url, headers=HEADERS, timeout=10, follow_redirects=True)
            r.raise_for_status()
            
            page_meta, page_sections = parse_html(r.text, current_url)
            if i == 0: meta = page_meta
            all_sections.extend(page_sections)
            
            next_link = find_next_page_static(BeautifulSoup(r.text, "html.parser"), current_url)
            if next_link and next_link not in visited_pages:
                interactions["clicks"].append(f"static_pagination: {next_link}")
                visited_pages.append(next_link)
                current_url = next_link
            else:
                break
        
        interactions["pages"] = visited_pages
        
        # --- FIX: Renumber IDs for Static Sections ---
        # Since we visited multiple pages, we might have duplicate "section-0"s.
        final_static_sections = []
        for i, sec in enumerate(all_sections):
            sec["id"] = f"section-{i}"
            final_static_sections.append(sec)
        
        # Prepare valid result object
        static_success_obj = {
            "result": {
                "url": url,
                "scrapedAt": scraped_at,
                "meta": meta,
                "sections": final_static_sections, # <--- Use the renumbered list
                "interactions": interactions,
                "errors": errors,
            }
        }

        # DECISION POINT:
        # If we have content AND depth >= 3, Static is sufficient. Return immediately.
        if len(final_static_sections) > 0 and len(visited_pages) >= 3:
            return static_success_obj
        
        # If we have content but NOT depth, save as backup and fall through to JS
        if len(final_static_sections) > 0:
            backup_result = static_success_obj

    except Exception as e:
        errors.append({"message": f"Static phase failed: {str(e)}", "phase": "static"})

    # ---- JS FALLBACK / ENHANCEMENT ----
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Reset accumulators for JS phase
            js_sections = []
            js_pages = [url]
            js_interactions = {"clicks": [], "scrolls": 0, "pages": [url]}
            
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 1. Scroll (Infinite Scroll Support)
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
                js_interactions["scrolls"] += 1
                js_interactions["clicks"].append("window.scrollTo(bottom)")
            
            # Parse after scrolling
            meta, sections = parse_html(page.content(), url)
            js_sections.extend(sections)
            
            # 2. Interactions (Load More / Next / Tabs)
            for _ in range(2):
                try:
                    next_loc = page.locator("button:has-text('Load more'), button:has-text('Show more'), a:has-text('Next'), a:has-text('More'), [role='tab']").first
                    
                    if next_loc.is_visible():
                         next_loc.click()
                         page.wait_for_load_state("networkidle")
                         page.wait_for_timeout(1500)
                         
                         curr_url = page.url
                         if curr_url not in js_pages:
                             js_pages.append(curr_url)
                             
                         # Accumulate new content
                         _, new_sections = parse_html(page.content(), curr_url)
                         js_sections.extend(new_sections)
                         js_interactions["clicks"].append("playwright_click: interactive_element")
                    else:
                        break
                except:
                    break

            js_interactions["pages"] = js_pages
            browser.close()

            # --- FIX: Renumber IDs for JS Sections ---
            final_js_sections = []
            for i, sec in enumerate(js_sections):
                sec["id"] = f"section-{i}" 
                final_js_sections.append(sec)

            return {
                "result": {
                    "url": url,
                    "scrapedAt": scraped_at,
                    "meta": meta,
                    "sections": final_js_sections, # <--- Use the renumbered list
                    "interactions": js_interactions,
                    "errors": errors,
                }
            }

    except Exception as e:
        errors.append({"message": str(e), "phase": "js"})
        
        # If JS crashed but we have a Static Backup, return that!
        if backup_result:
            backup_result["result"]["errors"].extend(errors)
            return backup_result

    # Final Fallback if everything failed
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