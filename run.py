import asyncio
import os
import json
import re
from pathlib import Path
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
from urllib.parse import urlparse


class DocumentationCrawler:
    def __init__(self, base_url, output_dir="output", resume=True):
        self.base_url = base_url.rstrip('/')
        self.output_dir = Path(output_dir)
        self.resume = resume
        self.visited_urls = set()
        self.queue = []
        self.state_file = self.output_dir / "crawler_state.json"
        self.base_domain = urlparse(base_url).netloc

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(exist_ok=True)

        # Load previous state if resuming
        if self.resume and self.state_file.exists():
            self._load_state()

    def _load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.visited_urls = set(state.get('visited_urls', []))
                self.queue = state.get('queue', [])
        except Exception as e:
            print(f"Error loading state: {e}")

    def _save_state(self):
        state = {
            'visited_urls': list(self.visited_urls),
            'queue': self.queue
        }
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"Error saving state: {e}")

    def _get_filename(self, url):
        # Remove fragment identifier
        url_without_fragment = url.split('#')[0]
        # Create a safe filename from URL
        path = url_without_fragment.replace(self.base_url, '').strip('/')
        if not path:
            path = "index"
        return f"{path}.md"

    def _process_markdown_links(self, markdown, page_url):
        """Convert absolute URLs to relative markdown links within docs"""
        base_path = urlparse(page_url).path.rsplit('#', 1)[0]

        # Convert absolute URLs to relative
        pattern = rf'\[(.*?)\]\({self.base_url}(.*?)\)'

        def replacer(match):
            text = match.group(1)
            link = match.group(2)
            # Keep fragment identifiers but make path relative
            if '#' in link:
                path, fragment = link.split('#', 1)
                if path == base_path:
                    return f'[{text}](#{fragment})'
                elif not path:
                    return f'[{text}](#{fragment})'
            return f'[{text}](.{link})'

        return re.sub(pattern, replacer, markdown)

    async def crawl(self):
        if not self.queue and self.base_url not in self.visited_urls:
            self.queue.append(self.base_url)

        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )

        run_config = CrawlerRunConfig(
            word_count_threshold=10,
            exclude_external_links=True,
            remove_overlay_elements=True,
            process_iframes=True,
            cache_mode=CacheMode.ENABLED,
            verbose=False
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            while self.queue:
                url = self.queue.pop(0)

                if url in self.visited_urls:
                    continue

                print(f"Crawling: {url}")

                result = await crawler.arun(url=url, config=run_config)

                if result.success:
                    # Save markdown content
                    filename = self._get_filename(url)
                    output_path = self.output_dir / filename

                    # Create parent directories if needed
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    # Process markdown to fix links
                    processed_markdown = self._process_markdown_links(
                        result.markdown, url)

                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(processed_markdown)

                    print(f"Saved: {output_path}")

                    # Extract links from the page
                    if hasattr(result, 'links') and 'internal' in result.links:
                        for link in result.links['internal']:
                            if 'href' in link:
                                new_url = link['href']
                                # Handle relative URLs
                                if new_url.startswith('/'):
                                    new_url = self.base_url + new_url
                                elif not new_url.startswith(('http://', 'https://')):
                                    new_url = self.base_url + '/' + new_url
                                # Remove fragment for URL tracking
                                base_url = new_url.split('#')[0]
                                if base_url.startswith(self.base_url) and base_url not in self.visited_urls:
                                    self.queue.append(base_url)

                self.visited_urls.add(url.split('#')[0])
                self._save_state()


async def main(base_url, noresume=False):
    crawler = DocumentationCrawler(base_url, resume=not noresume)
    await crawler.crawl()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Crawl documentation website and save pages as markdown files.')
    parser.add_argument(
        'url', help='Base URL of the documentation site to crawl')
    parser.add_argument('--noresume', action='store_true',
                        help='Do not resume from previous crawl')

    args = parser.parse_args()

    asyncio.run(main(args.url, args.noresume))
