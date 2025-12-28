# 🕸️ Universal Website Scraper (MVP)

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Playwright](https://img.shields.io/badge/Playwright-Enabled-green)
![Status](https://img.shields.io/badge/Status-Verified-success)

A robust **full-stack website scraping solution** designed for the modern web.  
It uses an intelligent **Hybrid Engine** that prioritizes **high-speed static extraction** and seamlessly upgrades to a **full browser environment (Playwright)** when required.

This enables reliable scraping of:
- JavaScript-heavy websites  
- Single Page Applications (SPAs)  
- Infinite scroll pages  
- Interactive UI elements  

---

## 🚀 Setup & Run

The project includes a **one-click setup script** that automatically handles:
- Virtual environment creation  
- Dependency installation  
- Playwright browser binaries  

### Prerequisites
- Python **3.10+**
- Active internet connection (for Playwright browser installation)

### Quick Start

Run the following commands from the project root:

```bash
chmod +x run.sh
./run.sh

## 🧪 Verified Test Matrix

This solution has been rigorously tested against diverse web architectures to ensure 100% compliance with assignment requirements.

| Feature Category | Verified On | Status | Description |
| :--- | :--- | :--- | :--- |
| **Pagination** | Hacker News | ✅ PASS | Detected static “More” links and recursively fetched 4+ pages via fast HTTP requests (Depth ≥ 3). |
| **Infinite Scroll** | Dev.to | ✅ PASS | Successfully simulated scroll events to trigger lazy-loading and captured dynamic content updates. |
| **SPA Interactions** | MUI Tabs | ✅ PASS | Identified and clicked interactive React elements (`[role='tab']`) to reveal hidden content. |
| **JS Rendering** | Next.js Docs / Vercel | ✅ PASS | Rendered client-side React content invisible to standard HTTP requests. |
| **Anti-Bot Handling** | Wikipedia | ✅ PASS | Handled 403 Forbidden by automatically falling back to browser-based scraping. |
| **Error Handling** | Unsplash | ✅ PASS | Detected aggressive bot protection (401/Captcha) and returned structured error logs instead of crashing. |

## 🏗️ Architecture: The Hybrid Strategy

To balance speed and capability, the scraper avoids a one-size-fits-all approach.

### Phase 1: Static Attempt (Fast Path)
* Fetches HTML using `httpx` with browser-mimicking headers.
* Parses content for pagination links (Next, Load More).
* Ideal for static or semi-static websites.

> **Result:** ⚡ Extremely fast extraction for sites like Hacker News, MDN, etc.

### Phase 2: Dynamic Upgrade (Fallback)
**Triggered when:**
* Static fetch fails (`403` / `401`).
* Insufficient content is returned.
* Pagination depth is less than required (Depth < 3).

**Actions:**
* Launches Playwright (Headless Chromium).
* Executes scrolling, button clicks, and SPA interactions.
* Captures dynamically rendered content.

---

## ⚠️ Known Limitations

### Execution Time
* **Static path:** Near-instant.
* **Dynamic fallback:** 10–30 seconds due to browser overhead.

### Hard Bot Blocks
* Enterprise-grade protections (e.g., Cloudflare “Under Attack” mode) may block even headless browsers.
* These cases are gracefully reported in the `errors[]` field of the JSON response instead of crashing the scraper.

## 📂 Project Structure

```text
.
├── run.sh              # Setup and entry-point script
├── scraper.py          # Core Hybrid Engine logic
├── server.py           # FastAPI/Flask server exposing /scrape endpoint
├── design_notes.md     # Architecture decisions and heuristics
└── capabilities.json   # Feature flags and scraper capabilities