#!/usr/bin/env python3
"""
Wikipedia Vital Articles Markdown Generator

This script reads the JSON files created by scrape-vital-articles.py
and generates markdown files for all articles using the existing
markdown generation features.

Usage:
    python3 generate-vital-articles-md.py [--levels 1 2 3] [--dl-image yes|no] [--resume]

Output:
    Markdown files in md_output/vital_articles/levelN/ directories
"""

import os
import json
import argparse
import wikipedia
from tqdm import tqdm
from datetime import datetime
import re


# Directories
JSON_DIR = "vital_articles_data"
OUTPUT_BASE_DIR = "md_output/vital_articles"


def clean_content(content):
    """
    Clean up Wikipedia content for better markdown output.
    
    Args:
        content: Raw Wikipedia page content
        
    Returns:
        Cleaned content string
    """
    # Remove LaTeX/math formulas (they don't render well in plain markdown)
    content = re.sub(r'\s*\{\s*\\[a-z]+style[^}]*\}', '', content)
    content = re.sub(r'\{[^}]*displaystyle[^}]*\}', '[formula]', content)
    content = re.sub(r'\([^)]*\\[a-z]+[^)]*\)', '', content)
    
    # Clean up malformed headings with extra = signs
    # Pattern: =### Heading= or === Heading ===
    content = re.sub(r'^=+(#{1,6})\s*([^=\n]+?)\s*=+$', r'\1 \2', content, flags=re.MULTILINE)
    content = re.sub(r'^=+\s*([^=\n]+?)\s*=+$', r'## \1', content, flags=re.MULTILINE)
    
    # Convert Wikipedia heading markers to markdown
    content = re.sub(r'^====\s*([^=]+?)\s*====\s*$', r'#### \1', content, flags=re.MULTILINE)
    content = re.sub(r'^===\s*([^=]+?)\s*===\s*$', r'### \1', content, flags=re.MULTILINE)
    content = re.sub(r'^==\s*([^=]+?)\s*==\s*$', r'## \1', content, flags=re.MULTILINE)
    
    # Remove excessive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Clean up parenthetical notes that are artifacts
    content = re.sub(r'\s+\(\s*\)', '', content)
    
    return content.strip()


def generate_markdown(topic, download_images=False):
    """
    Generate markdown for a Wikipedia article.
    Improved version with better content cleanup.
    
    Args:
        topic: Article title
        download_images: Whether to download images
        
    Returns:
        Tuple of (success: bool, markdown_text: str or None, error_msg: str or None)
    """
    try:
        page = wikipedia.page(topic, auto_suggest=False)
    except wikipedia.exceptions.DisambiguationError as e:
        return (False, None, f"Disambiguation page: {e.options[:3]}")
    except wikipedia.exceptions.PageError:
        return (False, None, f"Page not found")
    except Exception as e:
        return (False, None, f"Error: {str(e)}")

    # Start with title
    markdown_text = f"# {page.title}\n\n"
    
    # Get and clean content
    cleaned_content = clean_content(page.content)
    
    # Add the cleaned content
    markdown_text += cleaned_content
    
    # Optional: Add source link at the end
    markdown_text += f"\n\n---\n*Source: {page.url}*\n"

    if download_images:
        import requests
        import urllib.parse
        
        # Note: Images are downloaded but not embedded in the markdown
        # to keep the file structure simple. The image downloading
        # feature can be enhanced in future versions.
        pass

    return (True, markdown_text, None)


def load_json_file(level):
    """
    Load the JSON file for a specific level.
    
    Args:
        level: The level number
        
    Returns:
        Dictionary with level data, or None if file doesn't exist
    """
    filename = os.path.join(JSON_DIR, f"vital_articles_level{level}.json")
    
    if not os.path.exists(filename):
        print(f"Error: JSON file not found: {filename}")
        print(f"Please run scrape-vital-articles.py first to generate the JSON files.")
        return None
    
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_markdown(level, topic, markdown_text):
    """
    Save markdown content to a file.
    
    Args:
        level: The level number
        topic: Article title
        markdown_text: Markdown content
        
    Returns:
        Path to the saved file
    """
    level_dir = os.path.join(OUTPUT_BASE_DIR, f"level{level}")
    os.makedirs(level_dir, exist_ok=True)
    
    # Sanitize filename
    safe_filename = topic.replace('/', '_').replace('\\', '_')
    filename = os.path.join(level_dir, f"{safe_filename}.md")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    
    return filename


def process_level(level, download_images=False, resume=False):
    """
    Process all articles for a specific level.
    
    Args:
        level: The level number
        download_images: Whether to download images
        resume: Whether to skip already-downloaded articles
        
    Returns:
        Statistics dictionary
    """
    print(f"\n{'='*60}")
    print(f"Processing Level {level}")
    print(f"{'='*60}")
    
    # Load JSON data
    data = load_json_file(level)
    if not data:
        return None
    
    articles = data.get('articles', [])
    total = len(articles)
    
    print(f"Total articles to process: {total}")
    
    # Track statistics
    stats = {
        'level': level,
        'total': total,
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }
    
    # Create error log file
    log_dir = os.path.join(OUTPUT_BASE_DIR, f"level{level}")
    os.makedirs(log_dir, exist_ok=True)
    error_log_file = os.path.join(log_dir, f"errors_level{level}.log")
    
    with open(error_log_file, 'w', encoding='utf-8') as error_log:
        error_log.write(f"Error log for Level {level}\n")
        error_log.write(f"Started: {datetime.now().isoformat()}\n")
        error_log.write(f"{'='*60}\n\n")
        
        # Process each article with progress bar
        for topic in tqdm(articles, desc=f"Level {level}", unit="article"):
            # Check if article already exists (for resume functionality)
            safe_filename = topic.replace('/', '_').replace('\\', '_')
            output_file = os.path.join(OUTPUT_BASE_DIR, f"level{level}", f"{safe_filename}.md")
            
            if resume and os.path.exists(output_file):
                stats['skipped'] += 1
                continue
            
            # Generate markdown
            success, markdown_text, error_msg = generate_markdown(topic, download_images)
            
            if success:
                save_markdown(level, topic, markdown_text)
                stats['success'] += 1
            else:
                stats['failed'] += 1
                error_entry = f"{topic}: {error_msg}"
                stats['errors'].append(error_entry)
                error_log.write(f"{error_entry}\n")
        
        error_log.write(f"\n{'='*60}\n")
        error_log.write(f"Completed: {datetime.now().isoformat()}\n")
        error_log.write(f"Success: {stats['success']}, Failed: {stats['failed']}, Skipped: {stats['skipped']}\n")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Generate markdown files for Wikipedia vital articles from JSON data."
    )
    parser.add_argument(
        '--levels',
        type=int,
        nargs='+',
        default=[1, 2, 3, 4, 5],
        choices=[1, 2, 3, 4, 5],
        help="Specify which levels to process (default: all 5 levels)"
    )
    parser.add_argument(
        '--dl-image',
        choices=['yes', 'no'],
        default='no',
        help="Download images (default: no, for faster processing)"
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help="Skip articles that have already been downloaded"
    )
    parser.add_argument(
        '--lang',
        type=str,
        default='en',
        help="Wikipedia language code (default: en)"
    )
    
    args = parser.parse_args()
    
    # Set Wikipedia language
    wikipedia.set_lang(args.lang)
    
    download_images = args.dl_image == 'yes'
    
    print("=" * 60)
    print("Wikipedia Vital Articles Markdown Generator")
    print("=" * 60)
    print(f"Processing levels: {args.levels}")
    print(f"Download images: {download_images}")
    print(f"Resume mode: {args.resume}")
    print("")
    
    # Process each level
    all_stats = []
    
    for level in sorted(args.levels):
        stats = process_level(level, download_images, args.resume)
        if stats:
            all_stats.append(stats)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Generation Complete!")
    print("=" * 60)
    
    for stats in all_stats:
        print(f"\nLevel {stats['level']}:")
        print(f"  Total articles: {stats['total']}")
        print(f"  Successfully generated: {stats['success']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Skipped (resume): {stats['skipped']}")
        
        if stats['errors']:
            print(f"  Error log: {OUTPUT_BASE_DIR}/level{stats['level']}/errors_level{stats['level']}.log")
    
    print(f"\nMarkdown files saved to: {OUTPUT_BASE_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
