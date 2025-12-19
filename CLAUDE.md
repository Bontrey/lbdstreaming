# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a web scraping tool that fetches the top 12 popular films from Letterboxd's "Popular This Week" page and displays their streaming availability by scraping the "Where to watch" section from each film's individual page.

## Setup and Dependencies

Install dependencies:
```bash
pip3 install -r requirements.txt
```

System requirements:
- Chrome browser must be installed
- chromedriver must be installed: `brew install chromedriver` (macOS)

## Running the Script

```bash
python3 letterboxd_streaming.py
```

The script runs autonomously and outputs results to stdout.

## Architecture

### Web Scraping Approach

The script uses **Selenium with headless Chrome** (not just requests/BeautifulSoup) because Letterboxd uses JavaScript to render film content dynamically. Static HTML scraping will not find the film containers.

### Two-Phase Scraping

1. **Phase 1**: Scrape popular films list
   - URL: `https://letterboxd.com/films/popular/this/week/`
   - Extracts film slugs from `data-film-slug` attributes or anchor hrefs
   - Builds full URLs: `https://letterboxd.com/film/{slug}/`

2. **Phase 2**: Scrape each film's streaming info
   - Navigates to individual film pages
   - Looks for `div#watch` → `section.services` → `p.service` elements
   - Extracts streaming service names from CSS classes (e.g., `.service.-amazon` → "Amazon")

### HTML Structure Dependencies

The scraper relies on Letterboxd's specific HTML structure:
- Film containers: `li.poster-container` or fallback selectors
- Streaming section: `div#watch > section.services > p.service`
- Service identification: CSS classes like `-amazon`, `-netflix`, `-disney-plus`
- UI elements to skip: `-showmore` class

### Rate Limiting

The script includes deliberate delays:
- 2-3 second waits after page loads for JavaScript rendering
- 1 second delay between film page requests to avoid overwhelming Letterboxd servers

## Modifying the Scraper

If Letterboxd changes their HTML structure:
1. Check `scrape_letterboxd_popular()` for film container selectors
2. Check `scrape_streaming_info()` for streaming service selectors
3. The scraper already includes multiple fallback selector strategies

To scrape different film lists, modify the URL in `scrape_letterboxd_popular()` (line 39).

To change the number of films scraped, modify the `[:12]` slice in line 67.
