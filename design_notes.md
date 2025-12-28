# Design Notes

## Static vs JS Fallback
We attempt static scraping first. If extracted text is insufficient (<500 chars),
we fallback to Playwright for JS rendering.

## Wait Strategy for JS
- [x] Network idle
Details: After each scroll, we wait for network idle to ensure new content loads.

## Click & Scroll Strategy
- Click flows: None
- Scroll: window.scrollTo bottom repeated 3 times
- Stop: fixed depth = 3

## Section Grouping & Labels
We group by semantic tags (header, main, section, article, footer).
Labels come from headings or first 6 words of text.

## Noise Filtering & Truncation
Raw HTML is truncated at 1500 characters.
