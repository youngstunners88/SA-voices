"""
Browser Agent Implementation

Integrates browser-use for web automation capabilities.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Browser configuration"""
    headless: bool = True
    stealth: bool = True
    timeout: int = 30
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    allowed_domains: Optional[List[str]] = None
    blocked_domains: List[str] = field(default_factory=list)
    max_pages: int = 10
    screenshot_dir: Path = Path("./data/screenshots")


@dataclass
class BrowseResult:
    """Result of browsing operation"""
    success: bool
    url: str
    title: str
    content: str
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[Path] = None
    pages_visited: int = 0
    actions_taken: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        if self.actions_taken is None:
            self.actions_taken = []


class BrowserAgent:
    """
    Browser agent for web automation.
    
    Wraps browser-use library for SA Voices integration.
    """
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.config.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        self._browser = None
        self._agent = None
        self._initialized = False
    
    async def _initialize(self):
        """Initialize browser and agent"""
        if self._initialized:
            return
        
        try:
            from browser_use import Agent, Browser
            
            # Initialize browser
            browser_kwargs = {
                "headless": self.config.headless,
            }
            
            if self.config.proxy:
                browser_kwargs["proxy"] = self.config.proxy
            
            self._browser = Browser(**browser_kwargs)
            
            # Initialize agent
            agent_kwargs = {
                "browser": self._browser,
            }
            
            self._agent = Agent(**agent_kwargs)
            self._initialized = True
            
            logger.info("Browser agent initialized")
            
        except ImportError:
            logger.error("browser-use not installed. Run: pip install browser-use")
            raise
    
    def _is_url_allowed(self, url: str) -> bool:
        """Check if URL is allowed"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Check blocked domains
        for blocked in self.config.blocked_domains:
            if blocked in domain:
                return False
        
        # Check allowed domains
        if self.config.allowed_domains:
            return any(allowed in domain for allowed in self.config.allowed_domains)
        
        return True
    
    async def browse(
        self,
        task: str,
        start_url: Optional[str] = None,
        max_steps: int = 20,
        extract_structured: bool = False
    ) -> BrowseResult:
        """
        Browse the web to complete a task.
        
        Args:
            task: Description of what to do
            start_url: Optional starting URL
            max_steps: Maximum navigation steps
            extract_structured: Whether to extract structured data
        
        Returns:
            BrowseResult with content and metadata
        """
        import time
        start_time = time.time()
        
        await self._initialize()
        
        # Validate URL if provided
        if start_url and not self._is_url_allowed(start_url):
            return BrowseResult(
                success=False,
                url=start_url or "",
                title="",
                content="",
                error=f"URL not allowed: {start_url}"
            )
        
        try:
            # Run browser agent
            result = await self._agent.run(
                task=task,
                start_url=start_url,
                max_steps=max_steps
            )
            
            duration = time.time() - start_time
            
            # Extract structured data if requested
            extracted_data = {}
            if extract_structured and result.success:
                extracted_data = await self._extract_structured_data(result)
            
            # Take screenshot if successful
            screenshot_path = None
            if result.success:
                screenshot_path = await self._take_screenshot()
            
            return BrowseResult(
                success=result.success,
                url=result.url or start_url or "",
                title=result.title or "",
                content=result.content or "",
                extracted_data=extracted_data,
                screenshot_path=screenshot_path,
                pages_visited=len(result.visited_pages) if hasattr(result, 'visited_pages') else 1,
                actions_taken=result.actions if hasattr(result, 'actions') else [],
                duration_seconds=duration,
            )
            
        except Exception as e:
            logger.error(f"Browse failed: {e}")
            return BrowseResult(
                success=False,
                url=start_url or "",
                title="",
                content="",
                error=str(e),
                duration_seconds=time.time() - start_time,
            )
    
    async def search(
        self,
        query: str,
        engine: str = "google",
        max_results: int = 5
    ) -> List[Dict[str, str]]:
        """
        Search the web.
        
        Args:
            query: Search query
            engine: Search engine to use
            max_results: Maximum results to return
        
        Returns:
            List of search results
        """
        await self._initialize()
        
        search_task = f"Search for '{query}' using {engine} and return the top {max_results} results with titles and URLs"
        
        result = await self.browse(
            task=search_task,
            start_url=f"https://www.{engine}.com/search?q={query.replace(' ', '+')}"
        )
        
        if not result.success:
            return []
        
        # Parse results from content
        # This is simplified - real implementation would use structured extraction
        return [{"title": result.title, "url": result.url, "snippet": result.content[:200]}]
    
    async def extract_table(
        self,
        url: str,
        table_index: int = 0
    ) -> List[Dict[str, str]]:
        """
        Extract table data from a webpage.
        
        Args:
            url: Page URL
            table_index: Index of table to extract (if multiple)
        
        Returns:
            List of row dictionaries
        """
        task = f"Go to {url} and extract all data from table #{table_index}"
        
        result = await self.browse(
            task=task,
            start_url=url,
            extract_structured=True
        )
        
        return result.extracted_data.get("table", [])
    
    async def fill_form(
        self,
        url: str,
        form_data: Dict[str, str],
        submit: bool = True
    ) -> BrowseResult:
        """
        Fill a web form.
        
        Args:
            url: Form page URL
            form_data: Field names and values
            submit: Whether to submit the form
        
        Returns:
            BrowseResult after form submission
        """
        field_descriptions = ", ".join([f"{k}='{v}'" for k, v in form_data.items()])
        submit_text = " and submit it" if submit else ""
        
        task = f"Go to {url}, fill the form with {field_descriptions}{submit_text}"
        
        return await self.browse(task=task, start_url=url)
    
    async def download_file(
        self,
        url: str,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Download a file.
        
        Args:
            url: File URL
            output_path: Where to save the file
        
        Returns:
            Path to downloaded file or None
        """
        import aiohttp
        
        if not self._is_url_allowed(url):
            logger.warning(f"URL not allowed: {url}")
            return None
        
        if output_path is None:
            filename = urlparse(url).path.split('/')[-1] or "download"
            output_path = Path("./data/downloads") / filename
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.read()
                        output_path.write_bytes(content)
                        logger.info(f"Downloaded: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Download failed: HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None
    
    async def _take_screenshot(self) -> Optional[Path]:
        """Take screenshot of current page"""
        try:
            import time
            timestamp = int(time.time())
            screenshot_path = self.config.screenshot_dir / f"screenshot_{timestamp}.png"
            
            # This would use browser-use's screenshot capability
            # Simplified implementation
            
            return screenshot_path
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
    
    async def _extract_structured_data(self, result) -> Dict[str, Any]:
        """Extract structured data from browse result"""
        # This would use more sophisticated extraction
        # For now, return basic info
        return {
            "url": result.url if hasattr(result, 'url') else "",
            "title": result.title if hasattr(result, 'title') else "",
        }
    
    async def close(self):
        """Close browser and cleanup"""
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
        
        self._initialized = False
        logger.info("Browser agent closed")
    
    async def __aenter__(self):
        await self._initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Convenience function for quick browsing
async def quick_browse(task: str, url: Optional[str] = None) -> BrowseResult:
    """Quickly browse a URL for a task"""
    async with BrowserAgent() as agent:
        return await agent.browse(task=task, start_url=url)
