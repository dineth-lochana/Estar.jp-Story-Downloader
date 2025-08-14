import os
import re
import argparse
import requests
from bs4 import BeautifulSoup
import time

BASE_URL = "https://estar.jp/novels/{story_id}/viewer"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def get_total_pages(story_id):
    """Get page count from the first page."""
    url = BASE_URL.format(story_id=story_id)
    try:
        resp = requests.get(url, headers=HEADERS, params={"page": 1}, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        span = soup.find("span", class_="partition singlePage")
        if not span:
            raise ValueError("Could not find page count element.")
        text = span.get_text(strip=True)
        match = re.search(r"/(\d+)ページ", text)
        if not match:
            raise ValueError(f"Unexpected page count format: {text}")
        return int(match.group(1))
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch page count: {e}")


def sanitize_filename(name):
    """Discard invalids from filename."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def download_image(img_url, dest_folder):
    """Make sure we get images :)"""
    try:
        clean_url = img_url.split('?')[0] 
        filename = os.path.basename(clean_url)
        filepath = os.path.join(dest_folder, filename)
        
        if not os.path.exists(filepath):
            print(f"  Downloading image: {filename}")
            resp = requests.get(clean_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            with open(filepath, 'wb') as f:
                f.write(resp.content)
        return filename
    except Exception as e:
        print(f"  Failed to download image {img_url}: {e}")
        return f"[Failed to download: {os.path.basename(img_url)}]"


def extract_story_title(page_title):
    """Get story title from title."""
    title = page_title.replace("【本文】", "").strip()
    for delimiter in ["|", "｜", " - 小説投稿エブリスタ", "ページ"]:
        if delimiter in title:
            title = title.split(delimiter)[0].strip()
    return title


def scrape_story(story_id):
    """Start Backup."""
    print(f"Starting to scrape story ID: {story_id}")
    
    try:
        total_pages = get_total_pages(story_id)
        print(f"Total pages detected: {total_pages}")
        
        resp = requests.get(BASE_URL.format(story_id=story_id), headers=HEADERS, params={"page": 1}, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        title_element = soup.find('title')
        if not title_element:
            raise ValueError("Could not find page title")
            
        raw_title = title_element.get_text().strip()
        story_title = extract_story_title(raw_title)
        
        folder_name = f"{sanitize_filename(story_title)} - {story_id}"
        os.makedirs(folder_name, exist_ok=True)
        images_folder = os.path.join(folder_name, "images")
        os.makedirs(images_folder, exist_ok=True)
        
        print(f"Created folder: {folder_name}")
        
        last_text = None
        pages_scraped = 0
        
        for page in range(1, total_pages + 3):
            print(f"Scraping page {page}/{total_pages}...")
            
            try:
                resp = requests.get(
                    BASE_URL.format(story_id=story_id), 
                    headers=HEADERS, 
                    params={"page": page},
                    timeout=30
                )
                resp.raise_for_status()
                page_soup = BeautifulSoup(resp.text, "html.parser")
                
                body = page_soup.find("div", class_="mainBody")
                if not body:
                    print(f"No main body found on page {page}, stopping.")
                    break
                
                full_content = body.get_text(separator="\n", strip=True)
                
                # Check for duplicate content (indicates we've gone past the end)
                if last_text is not None and full_content == last_text:
                    print(f"Detected duplicate content at page {page}, stopping.")
                    break
                
                # Only stop if there's truly no content at all (no title, no content)
                if not full_content.strip():
                    print(f"Completely empty page at {page}, stopping.")
                    break
                
                page_title_element = page_soup.find('title')
                if page_title_element:
                    page_title = extract_story_title(page_title_element.get_text().strip())
                else:
                    page_title = f"{story_title} - Page {page}"
                
                images_found = 0
                for img in body.find_all('img'):
                    src = img.get('src')
                    if src:
                        filename = download_image(src, images_folder)
                        img.replace_with(f"[Image: images/{filename}]")
                        images_found += 1
                
                if images_found > 0:
                    print(f"  Found {images_found} image(s)")
                
                page_filename = os.path.join(folder_name, f"page_{page:03d}.txt")
                with open(page_filename, 'w', encoding='utf-8') as f:
                    f.write(f"{page_title}\n")
                    f.write("=" * len(page_title) + "\n\n")
                    f.write(full_content)
                
                last_text = full_content
                pages_scraped += 1
                
                time.sleep(0.5)
                
            except requests.RequestException as e:
                print(f"Network error on page {page}: {e}")
                break
            except Exception as e:
                print(f"Error processing page {page}: {e}")
                continue
        
        print(f"\nFinished scraping story '{story_title}'")
        print(f"Pages scraped: {pages_scraped}")
        print(f"Saved to folder: '{folder_name}'")
        
    except Exception as e:
        print(f"Fatal error: {e}")
        return False
    
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="ESTAR.jp novel scraper",
        epilog="Example: python scraper.py 17418503"
    )
    parser.add_argument('story_id', help='Story ID number (e.g., 17418503)')
    parser.add_argument('--delay', type=float, default=0.5, 
                       help='Delay between requests in seconds (default: 0.5)')
    
    args = parser.parse_args()
    
    # Make sure ID is a number.
    if not args.story_id.isdigit():
        print("Error: Story ID must be a number")
        exit(1)
    
    success = scrape_story(args.story_id)
    exit(0 if success else 1)