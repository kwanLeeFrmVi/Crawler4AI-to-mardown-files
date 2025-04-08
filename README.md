# Documentation Crawler
<a href="https://github.com/unclecode/crawl4ai">
  <img src="https://raw.githubusercontent.com/unclecode/crawl4ai/main/docs/assets/powered-by-dark.svg" alt="Powered by Crawl4AI" width="200"/>
</a>

``` 
This project uses Crawl4AI (https://github.com/unclecode/crawl4ai) for web data extraction.
```

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-performance Python tool for crawling and archiving documentation websites as properly linked markdown files.

## Features

- **Multi-threaded crawling** - Configurable number of concurrent workers (default: 5)
- **Resume capability** - Saves crawl state to continue interrupted sessions
- **Smart link conversion** - Converts absolute URLs to relative markdown links while preserving structure
- **Fragment handling** - Properly processes #anchor links within pages
- **State management** - Tracks visited URLs and queue in JSON state files
- **Configurable depth** - Control crawl depth with max_depth parameter
- **Exclusion patterns** - Skip specific URL patterns with exclude_regex

## Installation

### Prerequisites
- Python 3.7+
- pip package manager

### Recommended: Using Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate on macOS/Linux
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate
```

### Install from source
```bash
git clone https://github.com/yourusername/crawler4ai.git
cd crawler4ai
pip install -r requirements.txt
```

## Usage

### Basic Command
```bash
python run.py https://developer.example.com/docs
```

### Advanced Options
```bash
python run.py https://developer.example.com/docs \
  --noresume \
  --workers 8 \
  --max_depth 3 \
  --output ./my_docs \
  --exclude "/api/.*"
```

### Full Command Line Options

| Option          | Description                          | Default  |
|-----------------|--------------------------------------|----------|
| `url`           | Base URL to crawl                    | Required |
| `--noresume`    | Start fresh crawl                    | False    |
| `--workers`     | Concurrent workers                   | 5        |
| `--output`      | Output directory                     | ./output |
| `--max_depth`   | Maximum crawl depth (0=unlimited)    | 0        |
| `--exclude`     | Regex pattern for URLs to exclude    | None     |
| `--user_agent`  | Custom user agent string             | crawler4ai |
| `--timeout`     | Request timeout in seconds           | 30       |

## Configuration

For advanced configuration, edit `config.py`:

```python
# config.py
DEFAULT_SETTINGS = {
    'workers': 5,
    'timeout': 30,
    'user_agent': 'crawler4ai',
    'output_dir': './output',
    'state_file': './crawl_state.json',
    'max_retries': 3,
    'respect_robots': True
}
```

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Code Style
This project uses PEP 8 style guidelines. Please run before committing:
```bash
flake8 .
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Your Name - your.email@example.com  
Project Link: [https://github.com/yourusername/crawler4ai](https://github.com/yourusername/crawler4ai)
