from playwright.async_api import async_playwright
import asyncio

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await (await browser.new_context()).new_page()
        await page.goto("https://www.amazon.com")
        await page.wait_for_selector("#twotabsearchtextbox", timeout=10000)
        await page.fill("#twotabsearchtextbox", "macbook air")

        await page.wait_for_selector("#nav-search-submit-button", timeout=10000)
        await page.click("#nav-search-submit-button")

        await asyncio.sleep(5)

asyncio.run(run())
