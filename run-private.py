import asyncio
import json
import re
import argparse
import os
from pathlib import Path
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode


class PrivateDocumentationCrawler:
    def __init__(
        self,
        base_url: str,
        user_profile_dir: str,
        browser_type: str = "chromium",
        output_dir: str = "./output_private",
        resume: bool = True,
        max_workers: int = 5,
        max_depth: int = 0,
        exclude_pattern: str = None
    ):
        self.base_url = base_url
        self.user_profile_dir = Path(
            user_profile_dir).resolve()  # Ensure absolute path
        self.browser_type = browser_type
        self.output_dir = Path(output_dir)
        self.resume = resume
        self.max_workers = max_workers
        self.max_depth = max_depth  # 0 means unlimited depth
        self.exclude_pattern = re.compile(
            exclude_pattern) if exclude_pattern else None

        self.visited_urls = set()
        self.queue = {}  # Store URLs with their depth: {url: depth}
        self.lock = asyncio.Lock()
        self.state_file = self.output_dir / \
            "crawler_private_state.json"  # Use a different state file
        self.base_domain = urlparse(base_url).netloc

        if not self.user_profile_dir.exists() or not self.user_profile_dir.is_dir():
            raise ValueError(
                f"User profile directory does not exist or is not a directory: {self.user_profile_dir}")

        self.output_dir.mkdir(exist_ok=True)
        if self.resume and self.state_file.exists():
            self._load_state()

    def _load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.visited_urls = set(state.get('visited_urls', []))
                # Load queue preserving depth
                loaded_queue = state.get('queue', {})
                # Filter out already visited URLs from the loaded queue
                self.queue = {url: depth for url, depth in loaded_queue.items(
                ) if url not in self.visited_urls}
                print(
                    f"Resuming crawl. Loaded {len(self.visited_urls)} visited URLs and {len(self.queue)} URLs in queue.")
        except Exception as e:
            print(f"Error loading state: {e}. Starting fresh.")
            self.visited_urls = set()
            self.queue = {}

    async def _save_state(self):
        async with self.lock:
            # Only save URLs currently in the queue (not yet processed in this run)
            state = {
                'visited_urls': list(self.visited_urls),
                'queue': self.queue  # Save URLs with depth
            }
            try:
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
            except Exception as e:
                print(f"Error saving state: {e}")

    def _get_filename(self, url):
        # Remove fragment and base url
        url_no_fragment, _ = urldefrag(url)
        relative_path = url_no_fragment.replace(self.base_url, '').strip('/')

        # Handle potential query parameters by replacing unsafe chars
        safe_path = re.sub(r'[<>:"/\\|?*]', '_', relative_path)

        if not safe_path:
            safe_path = "index"

        # Ensure the path ends with .md
        if not safe_path.endswith('.md'):
            # If it looks like a file path already, add .md"
            if '.' in Path(safe_path).name:
                safe_path += ".md"
            # If it looks like a directory, add index.md
            else:
                safe_path = os.path.join(safe_path, "index.md")

        return safe_path

    def _process_markdown_links(self, markdown, page_url):
        # More robust link processing needed here, similar to run.py if complex relative links are expected
        # For now, keep it simple or adapt the logic from run.py's DocumentationCrawler
        # This basic version converts absolute links within the base_url domain to relative ones
        page_dir = Path(self._get_filename(page_url)).parent

        def replacer(match):
            text = match.group(1)
            full_link_url = match.group(2)

            # Ensure it's within the base domain
            if urlparse(full_link_url).netloc != self.base_domain:
                return match.group(0)  # Keep external links as they are

            link_no_fragment, fragment = urldefrag(full_link_url)
            target_filename = self._get_filename(link_no_fragment)
            target_path = self.output_dir / target_filename

            try:
                # Calculate relative path from the current file's directory to the target file
                relative_link = os.path.relpath(
                    target_path, start=(self.output_dir / page_dir))
                if fragment:
                    relative_link += f"#{fragment}"
                return f'[{text}]({relative_link})'
            except ValueError:  # Handle cases like different drives on Windows
                return match.group(0)  # Fallback to original link

        # Regex to find markdown links like [text](url)
        # Be careful with greedy matching, ensure URL part is captured correctly
        pattern = r'\[(.*?)\]\((https?://[^\)]+)\)'

        try:
            processed_markdown = re.sub(pattern, replacer, markdown)
        except Exception as e:
            print(f"Error processing links for {page_url}: {e}")
            processed_markdown = markdown  # Return original on error

        return processed_markdown

    def _normalize_url(self, href, base_url):
        """Normalizes a URL found in href, ensuring it's within the base domain and base path."""
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            return None

        # Resolve relative URLs
        full_url = urljoin(base_url, href)

        # Check if it's within the same domain
        if urlparse(full_url).netloc != self.base_domain:
            return None

        # Check if it starts with the base URL path
        if not full_url.startswith(self.base_url):
            # Allow links that are on the same domain but outside the specific base path if needed?
            # For strict documentation crawling, usually we want to stay within the base_url path.
            # Modify this check if broader same-domain crawling is desired.
            # print(f"Skipping URL outside base path: {full_url}")
            return None

        # Apply exclusion pattern if defined
        if self.exclude_pattern and self.exclude_pattern.search(full_url):
            # print(f"Excluding URL by pattern: {full_url}")
            return None

        # Remove fragment
        url_no_fragment, _ = urldefrag(full_url)
        return url_no_fragment

    async def _extract_links(self, html, page_url):
        """Extracts valid, normalized links from the HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        for link in soup.find_all('a', href=True):
            normalized_url = self._normalize_url(link['href'], page_url)
            if normalized_url:
                links.add(normalized_url)
        return links

    async def process_url(self, url, depth, crawler):
        """Processes a single URL: crawls, saves markdown, extracts links."""
        async with self.lock:
            if url in self.visited_urls:
                return
            # Check depth limit
            if self.max_depth > 0 and depth > self.max_depth:
                # print(f"Skipping URL due to depth limit ({depth} > {self.max_depth}): {url}")
                return
            self.visited_urls.add(url)
            # Remove from queue once processing starts
            self.queue.pop(url, None)

        print(f"Crawling (Depth {depth}): {url}")

        # Define specific run config for this URL
        run_config = CrawlerRunConfig(
            word_count_threshold=10,  # Adjust as needed
            exclude_external_links=False,  # We handle filtering in _normalize_url
            remove_overlay_elements=True,
            process_iframes=False,  # Usually not needed for docs, can enable if required
            cache_mode=CacheMode.ENABLED,  # Use caching
            wait_for="networkidle",  # Wait for page load
            page_timeout=30000,  # 30 second timeout
            verbose=False
        )

        # Retry mechanism for browser context errors
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                result = await crawler.arun(url=url, config=run_config)
                break  # Success, exit retry loop
            except Exception as e:
                error_message = str(e)
                if "Target page, context or browser has been closed" in error_message:
                    if attempt < max_retries:
                        print(f"Browser context error on {url}, retrying ({attempt}/{max_retries})...")
                        await asyncio.sleep(retry_delay * attempt)  # Exponential backoff
                        continue
                    else:
                        print(f"Failed after {max_retries} retries for {url}: {error_message}")
                        # Mark as visited but failed
                        async with self.lock:
                            if url in self.queue:
                                self.queue.pop(url)
                        await self._save_state()
                        return
                else:
                    # For other exceptions, log and continue
                    print(f"Error processing {url}: {error_message}")
                    await self._save_state()
                    return

        if result.success and result.markdown:
            # Check if the content is a login page
            if "Log In" in result.html or "Login" in result.html or "Sign In" in result.html:
                print(f"Detected login page. Skipping: {url}")
                return

            filename = self._get_filename(url)
            output_path = self.output_dir / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Process links *after* getting markdown
            processed_markdown = self._process_markdown_links(
                result.markdown, url)

            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(processed_markdown)
                print(f"Saved: {output_path}")
            except OSError as e:
                print(f"Error saving file {output_path}: {e}")

            # Extract links only if within depth limit for the *next* level
            if self.max_depth == 0 or depth < self.max_depth:
                new_urls = await self._extract_links(result.html, url)
                async with self.lock:
                    for new_url in new_urls:
                        # Add to queue only if not visited and not already queued
                        if new_url not in self.visited_urls and new_url not in self.queue:
                            self.queue[new_url] = depth + 1
                            # print(f"Added to queue (Depth {depth + 1}): {new_url}")
            else:
                print(f"Max depth reached for links from: {url}")

        elif not result.success:
            error_msg = result.error_message or "Unknown error"
            print(f"Crawl failed for {url}: {error_msg}")
            
            # Check for common error patterns and provide more detailed logs
            if "timeout" in error_msg.lower():
                print(f"  → Timeout error. Consider increasing page_timeout in CrawlerRunConfig.")
            elif "navigation" in error_msg.lower():
                print(f"  → Navigation error. Page might be redirecting or failing to load properly.")
            elif "context" in error_msg.lower() or "browser" in error_msg.lower():
                print(f"  → Browser context error. The browser session might have been interrupted.")

        # Save state periodically or after processing each URL
        await self._save_state()

    async def crawl(self):
        """Main crawling loop."""
        async with self.lock:
            if not self.queue and self.base_url not in self.visited_urls:
                # Start queue with base URL at depth 1
                # Check if base URL is excluded
                if self._normalize_url(self.base_url, self.base_url):
                    self.queue[self.base_url] = 1
                    print(
                        f"Initial URL added to queue (Depth 1): {self.base_url}")
                else:
                    print(
                        f"Base URL {self.base_url} is excluded or invalid. Cannot start crawl.")
                    return

        # Save state periodically or after processing each URL
        await self._save_state()

    async def crawl(self):
        """Main crawling loop."""
        async with self.lock:
            if not self.queue and self.base_url not in self.visited_urls:
                # Start queue with base URL at depth 1
                # Check if base URL is excluded
                if self._normalize_url(self.base_url, self.base_url):
                    self.queue[self.base_url] = 1
                    print(
                        f"Initial URL added to queue (Depth 1): {self.base_url}")
                else:
                    print(
                        f"Base URL {self.base_url} is excluded or invalid. Cannot start crawl.")
                    return

        browser_config = BrowserConfig(
            browser_type='chromium',
            headless=False,
            use_persistent_context=True,
            user_data_dir=str(self.user_profile_dir),
            verbose=True
        )

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                while True:
                    async with self.lock:
                        if not self.queue:
                            break
                        # Get items respecting max_workers limit
                        items_to_process = list(self.queue.items())[
                            :self.max_workers]

                        # Prepare batch: list of (url, depth) tuples
                        batch = [(url, depth) for url, depth in items_to_process]

                    if not batch:
                        # Wait if queue is temporarily empty but not finished
                        await asyncio.sleep(1)
                        continue

                    # Process URLs one by one with a small delay to avoid overwhelming the server
                    for url, depth in batch:
                        print(f"Processing: {url} (Depth: {depth})")
                        try:
                            await self.process_url(url, depth, crawler)
                        except Exception as e:
                            print(f"Unexpected error processing {url}: {str(e)}")
                            # Continue with next URL instead of failing the entire batch
                            continue
                        # Small delay between requests
                        await asyncio.sleep(0.5)
                    
                    # Save state after each batch completes
                    await self._save_state()
        except Exception as e:
            print(f"Critical crawler error: {str(e)}")
            # Save state before exiting due to critical error
            await self._save_state()

            print("\nCrawl completed!")


async def main(args):
    try:
        crawler = PrivateDocumentationCrawler(
            base_url=args.url,
            user_profile_dir=args.user_profile_dir,
            browser_type=args.browser_type,
            output_dir=args.output,
            resume=not args.noresume,
            max_workers=args.workers,
            max_depth=args.max_depth,
            exclude_pattern=args.exclude
        )
        await crawler.crawl()
    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Crawl a private documentation website using a persistent browser profile and save pages as markdown files.')

    parser.add_argument(
        'url',
        help='Base URL of the documentation site to crawl')
    parser.add_argument(
        '--user-profile-dir',
        required=True,
        help='Path to the browser user profile directory with login state')
    parser.add_argument(
        '--browser-type',
        type=str,
        default="chromium",
        help='Browser type to use (chromium, firefox, webkit)')
    parser.add_argument(
        '--output',
        default='./output_private',  # Different default output
        help='Output directory for Markdown files')
    parser.add_argument(
        '--noresume',
        action='store_true',
        help='Force a fresh crawl (do not resume from previous state)')
    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Number of concurrent workers')
    parser.add_argument(
        '--max-depth',
        type=int,
        default=0,  # 0 means unlimited
        help='Maximum crawl depth (0 for unlimited). 1 means only the base URL.')
    parser.add_argument(
        '--exclude',
        type=str,
        default=None,
        help='Regex pattern for URLs to exclude (e.g., "/api/.*")')

    args = parser.parse_args()

    # Basic validation for URL format
    if not args.url.startswith(('http://', 'https://')):
        print("Error: URL must start with http:// or https://")
    else:
        asyncio.run(main(args))
