#!/usr/bin/env python3
"""
Wikipedia Vital Articles Scraper

This script scrapes the Wikipedia vital articles lists from all 5 levels
and saves them as JSON files for further processing.

Usage:
    python3 scrape-vital-articles.py [--levels 1 2 3 4 5]

Output:
    JSON files in vital_articles_data/ directory, one per level.
"""

import os
import json
import argparse
import requests
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Set


# Base URL for vital articles
BASE_URL = "https://en.wikipedia.org"

# Output directory
OUTPUT_DIR = "vital_articles_data"


def is_valid_article_link(href: str) -> bool:
    """
    Check if a link is a valid Wikipedia article link.
    Filters out meta pages, navigation links, etc.
    """
    if not href or not href.startswith('/wiki/'):
        return False
    
    # Exclude Wikipedia meta pages and special pages
    excluded_prefixes = [
        '/wiki/Wikipedia:',
        '/wiki/Help:',
        '/wiki/Category:',
        '/wiki/File:',
        '/wiki/Template:',
        '/wiki/Template_talk:',  # Template talk pages
        '/wiki/Portal:',
        '/wiki/Portal_talk:',
        '/wiki/Special:',
        '/wiki/Talk:',
        '/wiki/User:',
        '/wiki/User_talk:',
        '/wiki/Wikipedia_talk:',
        '/wiki/MediaWiki:',
        '/wiki/MediaWiki_talk:',
        '/wiki/Module:',
        '/wiki/Module_talk:',
        '/wiki/Draft:',
        '/wiki/Draft_talk:',
    ]
    
    for prefix in excluded_prefixes:
        if href.startswith(prefix):
            return False
    
    # Exclude anchor links
    if '#' in href and href.index('#') < len(href) - 1:
        # Allow links with anchors only if the main article is included
        href = href.split('#')[0]
    
    return True


def extract_article_title(href: str) -> str:
    """
    Extract article title from Wikipedia URL and decode it.
    Example: /wiki/The_arts -> The_arts
    Example: /wiki/%C3%89cole -> École
    """
    if href.startswith('/wiki/'):
        title = href[6:].split('#')[0]  # Remove /wiki/ prefix and anchors
        # URL decode to convert percent-encoding to UTF-8
        title = urllib.parse.unquote(title)
        return title
    return href


def get_subpage_links(soup, level: int) -> List[str]:
    """
    Extract subpage links for levels that use subpages (levels 4-5).
    
    Args:
        soup: BeautifulSoup object of the main level page
        level: The level number (4 or 5)
        
    Returns:
        List of subpage URLs
    """
    subpage_links = []
    content_div = soup.find('div', {'id': 'mw-content-text'})
    
    if not content_div:
        return subpage_links
    
    # Pattern for subpage links: /wiki/Wikipedia:Vital_articles/Level/N/...
    subpage_pattern = f'/wiki/Wikipedia:Vital_articles/Level/{level}/'
    
    for link in content_div.find_all('a', href=True):
        href = link.get('href', '')
        
        # Check if this is a subpage link (not the main level page itself)
        if href.startswith(subpage_pattern) and href != f'/wiki/Wikipedia:Vital_articles/Level/{level}':
            # Exclude anchors and talk pages
            if '#' not in href and 'Talk:' not in href:
                full_url = BASE_URL + href
                if full_url not in subpage_links:
                    subpage_links.append(full_url)
    
    return subpage_links


def scrape_articles_from_page(url: str) -> Set[str]:
    """
    Scrape articles from a single page (either main level page or subpage).
    
    Args:
        url: URL of the page to scrape
        
    Returns:
        Set of article titles
    """
    headers = {
        'User-Agent': 'Wikipedia-Markdown-Generator/1.0 (https://github.com/erictherobot/wikipedia-markdown-generator; Educational purposes)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return set()
    
    soup = BeautifulSoup(response.content, 'lxml')
    content_div = soup.find('div', {'id': 'mw-content-text'})
    
    if not content_div:
        return set()
    
    articles: Set[str] = set()
    
    for link in content_div.find_all('a', href=True):
        href = link.get('href', '')
        
        if is_valid_article_link(href):
            title = extract_article_title(href)
            if title:
                articles.add(title)
    
    return articles


def scrape_page_with_subpages(url: str, level: int, depth: int = 0) -> Set[str]:
    """
    Recursively scrape a page that may have subpages.
    
    Args:
        url: URL of the page to scrape
        level: The level number (4 or 5)
        depth: Current recursion depth (for indentation)
        
    Returns:
        Set of article titles from this page and all its subpages
    """
    headers = {
        'User-Agent': 'Wikipedia-Markdown-Generator/1.0 (https://github.com/erictherobot/wikipedia-markdown-generator; Educational purposes)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"{'  ' * depth}Error fetching {url}: {e}")
        return set()
    
    soup = BeautifulSoup(response.content, 'lxml')
    
    # Check if this page has subpages
    subpage_pattern = url.rstrip('/') + '/'
    has_subpages = False
    nested_subpage_links = []
    
    content_div = soup.find('div', {'id': 'mw-content-text'})
    if content_div:
        for link in content_div.find_all('a', href=True):
            href = link.get('href', '')
            if href.startswith('/wiki/Wikipedia:Vital_articles/Level/'):
                full_url = BASE_URL + href
                # Check if this is a subpage of the current page
                if full_url.startswith(subpage_pattern) and full_url != url and '#' not in href and 'Talk:' not in href:
                    has_subpages = True
                    if full_url not in nested_subpage_links:
                        nested_subpage_links.append(full_url)
    
    # If this page has subpages, recursively scrape them
    if has_subpages and nested_subpage_links:
        all_articles: Set[str] = set()
        for subpage_url in nested_subpage_links:
            subpage_articles = scrape_page_with_subpages(subpage_url, level, depth + 1)
            all_articles.update(subpage_articles)
        return all_articles
    else:
        # No subpages, scrape articles from this page
        return scrape_articles_from_page(url)


def scrape_vital_articles_level(level: int) -> List[str]:
    """
    Scrape all article titles from a specific vital articles level page.
    For levels 4-5, this includes following subpage links recursively.
    
    Args:
        level: The level number (1-5)
        
    Returns:
        List of article titles
    """
    url = f"{BASE_URL}/wiki/Wikipedia:Vital_articles/Level/{level}"
    print(f"\nScraping Level {level} from {url}...")
    
    # Add User-Agent header to avoid 403 errors
    headers = {
        'User-Agent': 'Wikipedia-Markdown-Generator/1.0 (https://github.com/erictherobot/wikipedia-markdown-generator; Educational purposes)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching Level {level}: {e}")
        return []
    
    soup = BeautifulSoup(response.content, 'lxml')
    
    # For levels 4-5, check if there are subpages
    if level in [4, 5]:
        subpage_links = get_subpage_links(soup, level)
        
        if subpage_links:
            print(f"Found {len(subpage_links)} subpages for Level {level}")
            print(f"Scraping articles from subpages (may include nested subpages)...")
            
            articles: Set[str] = set()
            
            # Scrape each subpage (recursively if needed)
            for i, subpage_url in enumerate(subpage_links, 1):
                subpage_name = subpage_url.split('/')[-1]
                print(f"  [{i}/{len(subpage_links)}] Scraping {subpage_name}...", end=' ', flush=True)
                
                # Use recursive scraping to handle nested subpages
                subpage_articles = scrape_page_with_subpages(subpage_url, level)
                articles.update(subpage_articles)
                
                print(f"({len(subpage_articles)} articles)")
            
            article_list = sorted(list(articles))
            print(f"\nTotal unique articles found for Level {level}: {len(article_list)}")
            return article_list
    
    # For levels 1-3, or if no subpages found, scrape directly from main page
    print(f"Scraping articles from main page...")
    articles = scrape_articles_from_page(url)
    
    # Convert to sorted list for consistent output
    article_list = sorted(list(articles))
    
    print(f"Found {len(article_list)} unique articles for Level {level}")
    return article_list


def save_to_json(level: int, articles: List[str]) -> str:
    """
    Save articles list to a JSON file.
    
    Args:
        level: The level number
        articles: List of article titles
        
    Returns:
        Path to the saved JSON file
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    data = {
        "level": level,
        "count": len(articles),
        "scraped_at": datetime.now().isoformat(),
        "articles": articles
    }
    
    filename = os.path.join(OUTPUT_DIR, f"vital_articles_level{level}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {filename}")
    return filename


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Wikipedia vital articles lists and save to JSON files."
    )
    parser.add_argument(
        '--levels',
        type=int,
        nargs='+',
        default=[1, 2, 3, 4, 5],
        choices=[1, 2, 3, 4, 5],
        help="Specify which levels to scrape (default: all 5 levels)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Wikipedia Vital Articles Scraper")
    print("=" * 60)
    print(f"Scraping levels: {args.levels}")
    
    total_articles = 0
    
    for level in sorted(args.levels):
        articles = scrape_vital_articles_level(level)
        if articles:
            save_to_json(level, articles)
            total_articles += len(articles)
        else:
            print(f"Warning: No articles found for Level {level}")
    
    print("\n" + "=" * 60)
    print(f"Scraping complete!")
    print(f"Total articles scraped: {total_articles}")
    print(f"JSON files saved to: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
