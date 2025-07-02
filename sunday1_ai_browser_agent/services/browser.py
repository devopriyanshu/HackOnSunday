from playwright.async_api import async_playwright
import asyncio
import random
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
import json

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
        results = {
            "success": True,
            "actions": [],
            "screenshots": [],
            "final_url": None,
            "duration": 0
        }

        if not self.page or self.page.is_closed():
            await self.start()

        try:
            for action in actions:
                logger.info(f"➡️ Executing action: {json.dumps(action)}")
                await self._human_delay()
                action_result = await self._execute_single_action(action)
                results["actions"].append(action_result)
                logger.info(f"✅ Completed action: {action_result['action']} | Success: {action_result['success']}")

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
                try:
                    screenshot = await self._take_screenshot("error_final")
                    results["screenshots"].append(screenshot)
                except:
                    pass

        results["duration"] = round(time.time() - self.start_time, 2)
        return results

    async def _execute_single_action(self, action: Dict) -> Dict[str, Any]:
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
            try:
                result["screenshot"] = await self._take_screenshot(f"failed_{action_type}")
            except Exception as screenshot_error:
                logger.warning(f"Screenshot failed for {action_type}: {screenshot_error}")

        return result

    async def _handle_navigate(self, action: Dict) -> Dict:
        url = action.get("url")
        if not url:
            raise ValueError("Navigate action requires 'url'")

        await self.page.goto(url, timeout=60000, wait_until="networkidle")
        await self._human_delay(1.5, 2.5)
        return {"url": url, "status": "loaded"}

    async def _handle_input(self, action: Dict) -> Dict:
        text = action.get("text") or action.get("value")
        if not text:
            raise ValueError("Input action requires 'text' or 'value'")
        element = await self._locate_element(action)
        await self._human_type(element, text)
        return {"element": action.get("selector"), "text": text}

    async def _handle_click(self, action: Dict) -> Dict:
        element = await self._locate_element(action)
        await self._human_click(element)
        return {"element": action.get("selector")}

    async def _handle_wait(self, action: Dict) -> Dict:
        timeout = max(1000, min(10000, action.get("timeout", 5000)))
        if "selector" in action:
            await self.page.wait_for_selector(action["selector"], timeout=timeout)
            return {"wait_for": "selector", "selector": action["selector"]}
        else:
            await asyncio.sleep(timeout / 1000)
            return {"wait_for": "timeout", "ms": timeout}

    async def _locate_element(self, action: Dict) -> Any:
        if "selector" in action:
            return await self.page.wait_for_selector(action["selector"], timeout=5000)

        for fallback in action.get("fallbacks", []):
            try:
                return await self.page.wait_for_selector(fallback, timeout=2000)
            except:
                continue

        raise ValueError(f"Element not found using selector or fallbacks: {action}")

    async def _human_delay(self, min_delay=0.5, max_delay=1.5) -> None:
        await asyncio.sleep(random.uniform(min_delay, max_delay))

    async def _human_type(self, element: Any, text: str) -> None:
        await element.click(force=True)
        await asyncio.sleep(0.2)
        for char in text:
            await element.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))

    async def _human_click(self, element: Any) -> None:
        await element.hover()
        await asyncio.sleep(0.2)
        await element.click(delay=random.randint(50, 150))

    async def _take_screenshot(self, name: str) -> str:
        path = str(self.screenshots_dir / f"{name}_{int(time.time())}.png")
        await self.page.screenshot(path=path, full_page=True)
        return path

    async def _check_captcha(self) -> bool:
        return await self.page.query_selector("#captcha, .g-recaptcha, #recaptcha") is not None

    async def close(self) -> None:
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
