from playwright.async_api import async_playwright
import asyncio
from config import Config

async def run_browser_task(parsed_steps: dict):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=Config.BROWSER_HEADLESS)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(parsed_steps["url"])
            
            for action in parsed_steps["actions"]:
                if action["type"] == "input":
                    await page.fill(action["selector"], action["value"])
                elif action["type"] == "click":
                    await page.click(action["selector"])
                
                await asyncio.sleep(Config.ACTION_DELAY)

            final_url = page.url
            await context.close()
            await browser.close()
            
            return {"status": "success", "url": final_url}

    except Exception as e:
        return {"status": "error", "message": str(e)}