#!/usr/bin/env python3
"""
Script to scrape top 12 popular films from Letterboxd and check streaming availability
directly from Letterboxd's "Where to watch" section on each film's page.

Uses Selenium to handle JavaScript-rendered content.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cache file to store streaming info
CACHE_FILE = 'streaming_cache.json'


def load_cache():
    """Load cached streaming info from file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache):
    """Save streaming info cache to file."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save cache: {e}")


def setup_driver():
    """Set up a headless Chrome driver."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        print("Make sure you have Chrome and chromedriver installed.")
        print("You can install chromedriver via: brew install chromedriver (macOS)")
        return None


def scrape_letterboxd_popular(driver):
    """Scrape the first 12 popular films from Letterboxd with their URLs."""
    url = "https://letterboxd.com/films/popular/this/week/"

    print(f"Fetching popular films from {url}...")
    driver.get(url)

    # Wait for the film posters to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.poster-container, ul.poster-list li"))
        )
    except TimeoutException:
        print("Timeout waiting for films to load")
        return []

    # Give it a moment for all content to render
    time.sleep(2)

    # Get the page source and parse with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Try different selectors to find film containers
    film_containers = soup.select('li.poster-container')
    if not film_containers:
        film_containers = soup.select('ul.poster-list li')
    if not film_containers:
        film_containers = soup.select('li.listitem')

    films = []
    for container in film_containers[:12]:
        # Get the film poster div which contains the link
        poster_div = container.find('div', attrs={'data-film-slug': True})

        if not poster_div:
            # Try alternative approach - look for anchor tag
            anchor = container.find('a', href=True)
            if anchor and '/film/' in anchor['href']:
                film_slug = anchor['href'].replace('/film/', '').rstrip('/')
                poster_div = {'data-film-slug': film_slug}

                # Get title from img alt
                img = container.find('img')
                if img and img.get('alt'):
                    title = img['alt']
                else:
                    title = film_slug.replace('-', ' ').title()
            else:
                continue
        else:
            film_slug = poster_div.get('data-film-slug')
            img = poster_div.find('img')
            title = img.get('alt', film_slug.replace('-', ' ').title()) if img else film_slug.replace('-', ' ').title()

        if film_slug:
            film_url = f"https://letterboxd.com/film/{film_slug}/"
            films.append({
                'title': title,
                'url': film_url
            })

    return films


def scrape_streaming_info(driver, film_url):
    """Scrape the 'Where to watch' section from a film's Letterboxd page."""
    try:
        driver.get(film_url)

        # Wait for page to load - increased wait time
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Look for the div with id="watch"
        watch_div = soup.find('div', id='watch')

        if watch_div:
            # Look for the services section
            services_section = watch_div.find('section', class_='services')

            if services_section:
                # Find all service paragraphs
                service_paragraphs = services_section.find_all('p', class_='service')

                if service_paragraphs:
                    services = []
                    for service_p in service_paragraphs:
                        # Extract service name from the class
                        classes = service_p.get('class', [])
                        for cls in classes:
                            if cls.startswith('-') and cls != '-showmore':
                                # Clean up the service name
                                service_name = cls[1:].replace('-', ' ').title()
                                services.append(service_name)
                                break

                    if services:
                        # Remove duplicates while preserving order
                        unique_services = []
                        for s in services:
                            if s not in unique_services:
                                unique_services.append(s)
                        return ', '.join(unique_services)
            else:
                # Check if there's any content in the watch div
                # Sometimes films only have a message like "Watch it now"
                text = watch_div.get_text(strip=True)
                if text and 'trailer' not in text.lower():
                    # Extract meaningful text (not just "Where to watch")
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    filtered_lines = [line for line in lines if line.lower() not in ['where to watch', 'trailer']]
                    if filtered_lines:
                        return filtered_lines[0][:100]

        # If no watch div found, return message
        return "No streaming info available"

    except Exception as e:
        return f"Error: {str(e)}"


def scrape_film_worker(film_index, film, cache):
    """Worker function to scrape a single film's streaming info with its own driver."""
    # Check cache first
    if film['url'] in cache:
        return {
            'index': film_index,
            'title': film['title'],
            'url': film['url'],
            'streaming': cache[film['url']]['streaming'],
            'cached': True
        }

    driver = setup_driver()
    if not driver:
        return {
            'index': film_index,
            'title': film['title'],
            'url': film['url'],
            'streaming': "Error: Could not create driver",
            'cached': False
        }

    try:
        streaming_info = scrape_streaming_info(driver, film['url'])
        return {
            'index': film_index,
            'title': film['title'],
            'url': film['url'],
            'streaming': streaming_info,
            'cached': False
        }
    finally:
        driver.quit()


def main():
    print("=" * 70)
    print("LETTERBOXD POPULAR FILMS - STREAMING AVAILABILITY")
    print("=" * 70)
    print()

    # Load cache
    cache = load_cache()
    cache_size = len(cache)
    print(f"Loaded cache with {cache_size} film(s)\n")

    # Set up the Selenium driver
    driver = setup_driver()
    if not driver:
        return

    try:
        # Scrape Letterboxd popular films
        try:
            films = scrape_letterboxd_popular(driver)
            print(f"Found {len(films)} films\n")

            if len(films) == 0:
                print("No films found. The page structure may have changed.")
                print("Please check the Letterboxd website manually.")
                return
        except Exception as e:
            print(f"Error scraping Letterboxd: {e}")
            return

        # Check streaming for each film using parallel processing (max 3 concurrent)
        print("Fetching streaming info (checking cache first, max 3 concurrent requests)...\n")

        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all tasks
            futures = {
                executor.submit(scrape_film_worker, i + 1, film, cache): (i + 1, film)
                for i, film in enumerate(films)
            }

            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)

                    # Update cache if this was a new fetch and has valid streaming info
                    if not result.get('cached', False):
                        streaming = result['streaming']
                        # Only cache if we found actual streaming services (not errors or "no info")
                        should_cache = (
                            streaming and
                            not streaming.startswith('Not streaming') and
                            not streaming.startswith('Error:')
                        )

                        if should_cache:
                            cache[result['url']] = {
                                'title': result['title'],
                                'streaming': result['streaming']
                            }
                            save_cache(cache)
                            print(f"✓ Fetched & Cached: {result['title']}")
                        else:
                            print(f"✓ Fetched (not cached): {result['title']}")
                    else:
                        print(f"⚡ Cached: {result['title']}")
                except Exception as e:
                    film_index, film = futures[future]
                    print(f"✗ Error fetching {film['title']}: {e}")
                    results.append({
                        'index': film_index,
                        'title': film['title'],
                        'url': film['url'],
                        'streaming': f"Error: {str(e)}",
                        'cached': False
                    })

        # Sort results by original index and print summary
        results.sort(key=lambda x: x['index'])
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70 + "\n")

        cached_count = sum(1 for r in results if r.get('cached', False))
        fetched_count = len(results) - cached_count
        print(f"Summary: {cached_count} from cache, {fetched_count} newly fetched\n")

        for result in results:
            cached_indicator = " [CACHED]" if result.get('cached', False) else ""
            print(f"{result['index']}. {result['title']}{cached_indicator}")
            print(f"   URL: {result['url']}")
            print(f"   Streaming: {result['streaming']}")
            print()

        print("=" * 70)

    finally:
        # Clean up
        driver.quit()


if __name__ == "__main__":
    main()
