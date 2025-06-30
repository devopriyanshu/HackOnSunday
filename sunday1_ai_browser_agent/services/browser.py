# browser.py - Complete robust implementation
from playwright.async_api import async_playwright
import asyncio
import random
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrowserController:
    def __init__(self, headless: bool = False, slow_mo: int = 100):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless
        self.slow_mo = slow_mo
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        self.start_time = time.time()

    async def start(self) -> None:
        """Initialize browser with anti-detection measures"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--window-size=1366,768'
                ]
            )
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1366, 'height': 768},
                locale='en-US',
                timezone_id='America/New_York'
            )
            await self.context.add_init_script("""
                delete Object.getPrototypeOf(navigator).webdriver;
                window.navigator.chrome = { runtime: {} };
            """)
            self.page = await self.context.new_page()
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Browser initialization failed: {str(e)}")
            await self.close()
            raise

    async def execute_actions(self, actions: List[Dict]) -> Dict[str, Any]:
        """Execute actions with comprehensive error handling"""
        results = {
            "success": True,
            "actions": [],
            "screenshots": [],
            "final_url": None,
            "duration": 0
        }

        try:
            if not self.page or self.page.is_closed():
                await self.start()

            for action in actions:
                await self._human_delay()
                action_result = await self._execute_single_action(action)
                results["actions"].append(action_result)
                
                if not action_result["success"]:
                    results["success"] = False
                    if await self._check_captcha():
                        results["status"] = "captcha_required"
                    break

                if self.page and not self.page.is_closed():
                    screenshot = await self._take_screenshot(f"step_{len(results['actions'])}")
                    results["screenshots"].append(screenshot)

            if self.page and not self.page.is_closed():
                results["final_url"] = self.page.url

        except Exception as e:
            logger.error(f"Action execution failed: {str(e)}")
            results.update({
                "success": False,
                "error": str(e),
                "status": "failed"
            })
            if self.page and not self.page.is_closed():
                screenshot = await self._take_screenshot("error_final")
                results["screenshots"].append(screenshot)

        results["duration"] = round(time.time() - self.start_time, 2)
        return results

    async def _execute_single_action(self, action: Dict) -> Dict[str, Any]:
        """Execute a single action with validation"""
        action_type = action.get("type", "unknown")
        result = {
            "action": action_type,
            "success": False,
            "timestamp": time.time()
        }

        try:
            handler = getattr(self, f"_handle_{action_type}", None)
            if not handler:
                raise ValueError(f"Unsupported action type: {action_type}")

            result["details"] = await handler(action)
            result["success"] = True
            
            if self.page and not self.page.is_closed():
                result["screenshot"] = await self._take_screenshot(f"action_{action_type}")

        except Exception as e:
            logger.error(f"Action {action_type} failed: {str(e)}")
            result["error"] = str(e)
            if self.page and not self.page.is_closed():
                try:
                    result["screenshot"] = await self._take_screenshot(f"failed_{action_type}")
                except Exception as screenshot_error:
                    logger.error(f"Failed to take screenshot: {str(screenshot_error)}")
            raise

        return result

    async def _handle_navigate(self, action: Dict) -> Dict:
        """Handle navigation to URLs"""
        if "url" not in action:
            raise ValueError("Navigate action requires 'url' parameter")
        
        await self.page.goto(action["url"], timeout=60000, wait_until="networkidle")
        await self._human_delay()
        return {"url": action["url"], "status": "loaded"}

    async def _handle_input(self, action: Dict) -> Dict:
        """Handle text input with validation"""
        text = action.get("text") or action.get("value")
        if not text:
            raise ValueError("Input action requires 'text' or 'value'")
        
        element = await self._locate_element(action)
        await self._human_type(element, text)
        return {
            "element": action.get("selector") or action.get("element_description"),
            "text": text[:50] + "..." if len(text) > 50 else text
        }

    async def _handle_click(self, action: Dict) -> Dict:
        """Handle element clicking"""
        element = await self._locate_element(action)
        await self._human_click(element)
        return {"element": action.get("selector") or action.get("element_description")}

    async def _handle_submit(self, action: Dict) -> Dict:
        """Handle form submission"""
        await self.page.keyboard.press("Enter")
        await self._human_delay()
        return {"method": "keyboard_enter"}

    async def _handle_scroll(self, action: Dict) -> Dict:
        """Handle page scrolling"""
        direction = action.get("direction", "down")
        amount = max(100, min(2000, action.get("amount", 500)))
        
        if direction == "down":
            await self.page.mouse.wheel(0, amount)
        else:
            await self.page.mouse.wheel(0, -amount)
            
        await self._human_delay()
        return {"direction": direction, "pixels": amount}

    async def _handle_wait(self, action: Dict) -> Dict:
        """Handle waiting operations"""
        timeout = max(1000, min(10000, action.get("timeout", 5000)))
        
        if "selector" in action:
            await self.page.wait_for_selector(action["selector"], timeout=timeout)
            return {"wait_for": "selector", "selector": action["selector"]}
        else:
            await asyncio.sleep(timeout / 1000)
            return {"wait_for": "timeout", "ms": timeout}

    async def _locate_element(self, action: Dict) -> Any:
        """Smart element location with fallbacks"""
        strategies = []
        
        # Priority 1: Explicit selector
        if "selector" in action:
            return await self.page.wait_for_selector(
                action["selector"],
                timeout=action.get("timeout", 5000),
                state="attached"
            )
        
        # Priority 2: Element description
        if "element_description" in action:
            desc = action["element_description"]
            strategies.extend([
                f"text={desc} >> visible=true",
                f"[aria-label='{desc}'] >> visible=true",
                f"[placeholder='{desc}'] >> visible=true",
                f"text={desc}",
                f":has-text('{desc}')"
            ])
        
        # Priority 3: Fallback selectors
        strategies.extend(action.get("fallbacks", []))
        
        # Try all strategies
        for selector in strategies:
            try:
                element = await self.page.wait_for_selector(
                    selector,
                    timeout=2000,
                    state="attached"
                )
                if element:
                    return element
            except Exception:
                continue
        
        raise ValueError(f"Element not found using any strategy: {action}")

    async def _human_delay(self) -> None:
        """Randomized delay between actions"""
        await asyncio.sleep(random.uniform(0.5, 2.0))

    async def _human_type(self, element: Any, text: str) -> None:
        """Human-like typing simulation"""
        await element.click()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        for char in text:
            await element.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.2))

    async def _human_click(self, element: Any) -> None:
        """Human-like clicking simulation"""
        await element.hover()
        await asyncio.sleep(random.uniform(0.1, 0.5))
        await element.click(delay=random.randint(50, 150))

    async def _take_screenshot(self, name: str) -> str:
        """Capture and save screenshot"""
        path = str(self.screenshots_dir / f"{name}_{int(time.time())}.png")
        await self.page.screenshot(path=path, full_page=True)
        return path

    async def _check_captcha(self) -> bool:
        """Check for CAPTCHA presence"""
        return await self.page.query_selector("#captcha, .g-recaptcha, #recaptcha")

    async def close(self) -> None:
        """Proper resource cleanup"""
        try:
            if hasattr(self, 'page') and self.page and not self.page.is_closed():
                await self.page.close()
            if hasattr(self, 'context') and self.context:
                await self.context.close()
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
            logger.info("Resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None

async def run_workflow(actions: List[Dict]) -> Dict:
    """Helper function to run actions in a managed session"""
    controller = BrowserController(headless=False)
    try:
        return await controller.execute_actions(actions)
    finally:
        await controller.close()