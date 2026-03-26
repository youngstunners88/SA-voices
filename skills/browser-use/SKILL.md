# Browser-Use Skill

Web browsing automation for SA Voices agent.

## Overview

This skill integrates browser-use to enable the SA Voices agent to:
- Browse websites autonomously
- Extract information from web pages
- Fill forms and interact with web elements
- Take screenshots
- Download files

## Installation

```bash
pip install browser-use
playwright install chromium
```

## Usage

```python
from skills.browser_use import BrowserAgent

# Initialize browser agent
agent = BrowserAgent()

# Perform task
result = await agent.browse(
    task="Find information about South African languages on Wikipedia",
    start_url="https://en.wikipedia.org/wiki/Languages_of_South_Africa"
)

print(result.content)
print(result.screenshot_path)
```

## Features

- **Autonomous Browsing**: Navigate and interact with websites
- **Information Extraction**: Extract structured data from pages
- **Screenshot Capture**: Visual documentation of browsing
- **Form Filling**: Automated form completion
- **Multi-tab Support**: Handle multiple browser tabs
- **Stealth Mode**: Avoid detection as automation

## Configuration

```yaml
browser_use:
  headless: true
  stealth: true
  timeout: 30
  user_agent: "SA-Voices-Agent/1.0"
  proxy: null
  viewport:
    width: 1920
    height: 1080
```

## Safety

- URL whitelist/blacklist support
- Rate limiting
- Content filtering
- Automatic cookie handling
