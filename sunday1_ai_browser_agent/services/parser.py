from openai import OpenAI
import json
from config import Config
import asyncio

client = OpenAI(api_key=Config.OPENAI_API_KEY)

async def parse_command(nl_command: str) -> dict:
    system_prompt = """
You are an assistant that converts natural language commands into structured browser automation instructions using JSON format. 
The format must include a 'url' and a list of 'actions'. Each action must have:
- type: input or click
- selector: a CSS selector (prefer IDs or specific classes)
- value: only for 'input' type

Example for: "Search for MacBooks on Amazon":
{
  "url": "https://www.amazon.com",
  "actions": [
    {"type": "input", "selector": "#twotabsearchtextbox", "value": "MacBook"},
    {"type": "click", "selector": "#nav-search-submit-button"}
  ]
}
"""
    try:
        # Run the synchronous OpenAI call in a thread pool
        def sync_chat_completion():
            return client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Command: \"{nl_command}\""}
                ],
                temperature=0.2
            )
        
        # Run the synchronous code in an executor
        response = await asyncio.get_event_loop().run_in_executor(
            None, 
            sync_chat_completion
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        return {"error": f"Command parsing error: {str(e)}"}