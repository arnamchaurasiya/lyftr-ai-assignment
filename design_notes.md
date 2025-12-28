# Design Notes

## Static vs JS Fallback
- **Strategy:** I implemented a **"Static-Priority, Hybrid Fallback"** strategy. The system first attempts a high-speed HTTP request using `httpx`. It parses the static HTML to check for pagination links. If it can successfully traverse $\ge$ 3 pages statically, it returns the result immediately. If the static fetch fails (e.g., 403 Forbidden, 401 Unauthorized) or returns insufficient content (depth < 3), the system automatically upgrades to a **Playwright** browser instance to handle JavaScript rendering, infinite scrolling, and SPA interactions.

## Wait Strategy for JS
- [x] Network idle
- [x] Fixed sleep
- [x] Wait for selectors
- **Details:** The system uses `domcontentloaded` for initial page loads to ensure the DOM exists. For interactions (like clicking tabs or "Load More"), it waits for `networkidle` to ensure API requests complete. Short fixed sleeps (`1000ms`) are used specifically after scroll operations to give scroll-event listeners time to trigger lazy loading.

## Click & Scroll Strategy
- **Click flows implemented:** The scraper targets "functional" elements first: buttons containing text like "Load more", "Show more", or "Next", and elements with `[role='tab']`. As a fallback for marketing sites (like Vercel), it looks for internal navigation links in the `<header>` or `<nav>` to explore the site structure.
- **Scroll / pagination approach:**
    - **Infinite Scroll:** Executes `window.scrollTo(0, document.body.scrollHeight)` 3 times with a pause to trigger content expansion.
    - **Pagination:** Extracts absolute URLs from "Next" links and recursively visits them using efficient HTTP requests where possible.
- **Stop conditions:** The loop terminates strictly after 3 pages are visited, 3 scroll actions are performed, or if no interactive elements/links are found in the viewport.

## Section Grouping & Labels
- **How you group DOM into sections:** I implemented a **Heading-Based Partitioning** logic. The parser iterates linearly through the DOM. When it encounters a Header (`h1`, `h2`, `h3`) or a `<section>` tag, it initializes a new "Section Object". All subsequent sibling elements (paragraphs, lists, images) are accumulated into that section until the next Header is encountered.
- **How you derive section `type` and `label`:**
    - **Label:** Derived directly from the text content of the Heading element that started the section. If the section starts without a header (e.g., the top of the page), it defaults to "Introduction" or "Section".
    - **Type:** Defaults to `section`.

## Noise Filtering & Truncation
- **What you filter out:** During the navigation fallback, specific keywords like "Login", "Sign up", and "Home" are explicitly ignored to ensure the scraper focuses on content pages rather than utility pages. Empty strings and whitespace-only text nodes are stripped during extraction.
- **How you truncate `rawHtml` and set `truncated`:**
    - `rawHtml` is sliced to the first **1000 characters** to ensure the JSON payload remains lightweight.
    - `content.text` is limited to **5000 characters**.
    - The `truncated` boolean field is set to `True` whenever these limits are applied.