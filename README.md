# Documentation Crawler
<a href="https://github.com/unclecode/crawl4ai">
  <img src="https://raw.githubusercontent.com/unclecode/crawl4ai/main/docs/assets/powered-by-dark.svg" alt="Powered by Crawl4AI" width="200"/>
</a>

This project is designed to crawl documentation websites and convert them into a folder of well-structured Markdown files. These files can then be used directly for offline viewing with Obsidian or integrated into a Retrieval-Augmented Generation (RAG) workflow.

``` 
This project uses Crawl4AI (https://github.com/unclecode/crawl4ai) for web data extraction.
```
---

## Overview

The Documentation Crawler leverages the Crawl4AI tool to:
- **Crawl and extract** documentation pages from a given URL.
- **Convert** each page into Markdown with smart link conversion (absolute to relative).
- **Preserve** the structure and in-page navigation by handling URL fragments (e.g., `#anchor` links).
- **Store** the output in a structured folder for easy offline access and further processing.

---

## Key Features

- **Multi-threaded Crawling:** Utilize multiple workers (default: 5) to speed up the extraction process.
- **Resume Capability:** Continue interrupted crawl sessions by saving and restoring state via JSON files.
- **Smart Link Conversion:** Absolute URLs are converted to relative Markdown links, preserving navigation.
- **Fragment Handling:** Maintains in-page anchor links for proper navigation between sections.
- **Configurable Crawl Depth and Exclusions:** Limit the depth of the crawl and exclude unwanted URL patterns using regex filters.
- **Customizable Settings:** Adjust parameters like workers, timeouts, and user agent either via command line options or by editing the `config.py` file.

---

## Installation

### Prerequisites

- **Python 3.7+:** Ensure you have Python 3.7 or later.
- **pip:** Make sure pip is installed to manage dependencies.

### Setting Up a Virtual Environment

It is recommended to use a virtual environment:

```bash
# Create and activate the virtual environment
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Install from Source

Clone the repository and install dependencies:

```bash
git clone https://github.com/yourusername/crawler4ai.git
cd crawler4ai
pip install -r requirements.txt
```

---

## Usage

### Basic Command

Run the crawler with a base URL:

```bash
python run.py https://developer.example.com/docs
```

### Private Documentation Crawling

For crawling private documentation that requires authentication, use `run-private.py` with your browser profile. This approach opens a browser window where you can manually log in, and then the crawler will use your authenticated session to access protected content.

```bash
python run-private.py https://your-private-site.com/docs \
  --user-profile-dir "/path/to/browser/profile" \
  --output ./private_docs \
  --noresume
```

#### Browser Profile Locations

- **Chrome/Chromium (default)**: `~/Library/Application Support/Google/Chrome/Default`
- **Microsoft Edge**: `~/Library/Application Support/Microsoft Edge/Default`
- **Firefox**: `~/Library/Application Support/Firefox/Profiles/[profile-id]`

#### Tips for Private Crawling

- The browser will open in non-headless mode so you can log in manually if needed
- Use `--noresume` for a fresh crawl if you encounter issues
- Set `--max-depth` to limit how deep the crawler will go (e.g., `--max-depth 3`)
- The crawler processes pages sequentially to avoid overwhelming authentication systems

#### Additional Options for Private Crawling

| Option                | Description                         | Default   |
|-----------------------|-------------------------------------|-----------|
| `--user-profile-dir`  | Path to browser profile with login state | Required |
| `--browser-type`      | Browser type (chromium, firefox, webkit) | chromium |
| `--browser-dir`       | Path to browser executable          | None      |
| `--timeout`           | Request timeout in seconds          | 30        |

Note: The browser profile directory must contain your authenticated session. For Chrome on macOS, this is typically located at `~/Library/Application Support/Google/Chrome/Default`.

### Advanced Command Options

Customize the crawl with additional parameters:

```bash
python run.py https://developer.example.com/docs \
  --noresume \         # Start a fresh crawl without resuming
  --workers 8 \        # Use 8 concurrent workers
  --max_depth 3 \      # Limit the crawl to 3 levels deep
  --output ./my_docs \ # Save the Markdown files into ./my_docs folder
  --exclude "/api/.*"  # Exclude any URLs matching the pattern (e.g., API endpoints)
```

#### Full Command-Line Options

| Option          | Description                         | Default   |
|-----------------|-------------------------------------|-----------|
| `url`           | Base URL of the documentation site  | Required  |
| `--noresume`    | Force a fresh crawl (no state resume)| False    |
| `--workers`     | Number of concurrent workers        | 5         |
| `--output`      | Output directory for Markdown files | `./output`|
| `--max_depth`   | Maximum crawl depth (0 = unlimited) | 0         |
| `--exclude`     | Regex pattern for URLs to exclude   | None      |
| `--user_agent`  | Custom user agent string            | crawler4ai|
| `--timeout`     | Request timeout in seconds          | 30        |

---

## RAG Integration Workflow

This section explains how to integrate the downloaded Markdown documentation into a RAG (Retrieval-Augmented Generation) setup.

### 1. Prepare Markdown Files

After running the crawler, all documentation will be available as Markdown files (e.g., in the `./my_docs` folder). You can further process these files by:
- **Cleaning and Splitting:** Breaking large files into manageable chunks.
- **Metadata Enrichment:** Adding tags or extra context if necessary.

### 2. Embed and Index the Text

1. **Vectorization:**  
   Use an embedding model (like Sentence Transformers or OpenAI embeddings) to convert each text chunk into vector representations.
   
2. **Store Vectors:**  
   Save these vectors in a vector database (e.g., FAISS, Pinecone, or Weaviate) to enable efficient similarity searches.

### 3. Retrieval Mechanism for Generation

When a user query is received:
- **Retrieve:** Query the vector database to fetch the most relevant Markdown snippets.
- **Augment:** Pass both the query and the retrieved documents to your language model.
  
This combined context allows the model to generate more informed and precise answers.

---

## Viewing in Obsidian

To easily browse the downloaded Markdown documentation, you can use Obsidian as follows:

1. **Open Obsidian:**  
   Download and launch Obsidian from [obsidian.md](https://obsidian.md/).

2. **Set Up a New Vault:**
   - Choose "Open folder as vault" or "Create new vault" from the Obsidian menu.
   - Point to your output folder (e.g., `./my_docs`).

3. **Explore Your Documentation:**
   - Obsidian will automatically index and display all Markdown files.
   - Smart link conversion ensures that your internal navigation between files works seamlessly.
   - Utilize Obsidian’s Graph View, search, and backlink features to enhance your exploration experience.

---

## Contributing and Development

### Running Tests

Before committing any changes, ensure that your modifications are well-tested:

```bash
python -m pytest tests/
```

### Code Style

Follow PEP 8 guidelines by using:

```bash
flake8 .
```

### Contributing Workflow

1. **Fork the Repository**
2. **Create a Feature Branch:**  
   `git checkout -b feature/YourFeatureName`
3. **Commit Changes:**  
   `git commit -m 'Describe your feature or fix'`
4. **Push to Branch:**  
   `git push origin feature/YourFeatureName`
5. **Submit a Pull Request**

---

With this setup, you can easily generate a local archive of documentation in Markdown, view it in Obsidian, and integrate it into a RAG system to enhance your search and query responses. Enjoy your documentation crawling and retrieval-augmented generation journey!
