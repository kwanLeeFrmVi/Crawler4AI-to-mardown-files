import asyncio
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup


class DocumentationCrawler:
    def __init__(self, base_url, output_dir="output", resume=True, max_workers=5):
        self.base_url = base_url.rstrip('/')
        self.output_dir = Path(output_dir)
        self.resume = resume
        self.visited_urls = set()
        self.queue = []
        self.lock = asyncio.Lock()
        self.state_file = self.output_dir / "crawler_state.json"
        self.max_workers = max_workers
        self.base_domain = urlparse(base_url).netloc

        self.output_dir.mkdir(exist_ok=True)
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

    async def _save_state(self):
        async with self.lock:
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
        url_without_fragment = url.split('#')[0]
        path = url_without_fragment.replace(self.base_url, '').strip('/')
        if not path:
            path = "index"
        return f"{path}.md"

    def _process_markdown_links(self, markdown, page_url):
        base_path = urlparse(page_url).path.rsplit('#', 1)[0]

        pattern = rf'\[(.*?)\]\({self.base_url}(.*?)\)'

        def replacer(match):
            text = match.group(1)
            link = match.group(2)
            if '#' in link:
                path, fragment = link.split('#', 1)
                if path == base_path:
                    return f'[{text}](#{fragment})'
                elif not path:
                    return f'[{text}](#{fragment})'
            return f'[{text}](.{link})'

        return re.sub(pattern, replacer, markdown)

    async def _extract_links(self, html, base_url):
        soup = BeautifulSoup(html, 'html.parser')
        links = set()

        # Find all navigation links
        nav_links = soup.select('nav a, aside a, .sidebar a, .menu a')
        for link in nav_links:
            href = link.get('href')
            if href:
                full_url = self._normalize_url(href, base_url)
                if full_url:
                    links.add(full_url)

        # Find all content links
        content_links = soup.select('a')
        for link in content_links:
            href = link.get('href')
            if href:
                full_url = self._normalize_url(href, base_url)
                if full_url:
                    links.add(full_url)

        return links

    def _normalize_url(self, href, base_url):
        if href.startswith(('http://', 'https://')):
            if urlparse(href).netloc != self.base_domain:
                return None
            return href.split('#')[0]

        # Handle relative URLs
        full_url = urljoin(base_url, href)
        if not full_url.startswith(self.base_url):
            return None

        return full_url.split('#')[0]

    async def process_url(self, url, crawler):
        async with self.lock:
            if url in self.visited_urls:
                return
            self.visited_urls.add(url.split('#')[0])

        print(f"\nCrawling: {url}")

        result = await crawler.arun(url=url, config=self.run_config)

        if result.success:
            filename = self._get_filename(url)
            output_path = self.output_dir / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            processed_markdown = self._process_markdown_links(
                result.markdown, url)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(processed_markdown)

            print(f"Saved: {output_path}")

            # Extract links from both navigation and content
            new_urls = await self._extract_links(result.html, url)

            async with self.lock:
                for new_url in new_urls:
                    if new_url not in self.visited_urls and new_url not in self.queue:
                        self.queue.append(new_url)
                        print(f"Added to queue: {new_url}")

        await self._save_state()

    async def crawl(self):
        if not self.queue and self.base_url not in self.visited_urls:
            self.queue.append(self.base_url)
            print(f"Initial URL added to queue: {self.base_url}")

        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=650,
            viewport_height=2000,
            verbose=False
        )

        self.run_config = CrawlerRunConfig(
            word_count_threshold=10,
            exclude_external_links=True,
            remove_overlay_elements=True,
            process_iframes=True,
            cache_mode=CacheMode.DISABLED,
            excluded_tags=["form", "header", "footer"],
            excluded_selector=".header, .footer, .rm-Header",
            verbose=False
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            while True:
                async with self.lock:
                    if not self.queue:
                        break
                    batch = []
                    for _ in range(min(self.max_workers, len(self.queue))):
                        if self.queue:
                            batch.append(self.queue.pop(0))

                tasks = [self.process_url(url, crawler) for url in batch]
                await asyncio.gather(*tasks)

            print("\nCrawl completed successfully!")


async def main(base_url, noresume=False, workers=5):
    crawler = DocumentationCrawler(
        base_url, resume=not noresume, max_workers=workers)
    await crawler.crawl()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Crawl documentation website and save pages as markdown files.')
    parser.add_argument(
        'url', help='Base URL of the documentation site to crawl')
    parser.add_argument('--noresume', action='store_true',
                        help='Do not resume from previous crawl')
    parser.add_argument('--workers', type=int, default=5,
                        help='Number of concurrent workers')

    args = parser.parse_args()

    asyncio.run(main(args.url, args.noresume, args.workers))
