from openai import OpenAI
import json
import os
from config import Config
from typing import List, Dict, Optional
from sites import SITE_CONFIGS  # Your hardcoded selector map

client = OpenAI(api_key=Config.OPENAI_API_KEY)

class BrowserAction:
    def __init__(self, action_type: str, **kwargs):
        self.type = action_type
        self.params = kwargs
    
    def to_dict(self):
        return {"type": self.type, **self.params}
    
async def parse_command(nl_command: str) -> dict:
    """
    Main entry point for parsing natural language commands
    """
    try:
        # First, understand the command intent
        interpretation = await interpret_command(nl_command)
        
        if "error" in interpretation:
            return interpretation
        
        # For general commands, generate actions directly
        if interpretation.get("is_general", False):
            return generate_general_actions(interpretation)
        
        # For specific site commands, map to hardcoded selectors
        return map_to_selectors(interpretation)
        
    except Exception as e:
        return {
            "error": f"Command parsing error: {str(e)}",
            "actions": [{"type": "navigate", "url": "https://www.google.com"}]
        }
    

async def interpret_command(nl_command: str) -> dict:
    """
    Enhanced interpreter that identifies both specific and general commands
    """
    system_prompt = """
    Analyze browser automation commands and determine:
    1. Is this a general navigation command (is_general: true/false)
    2. Intent (search, navigate, login, etc.)
    3. Site (amazon, google, github, etc. or 'generic')
    4. Parameters (query, credentials, etc.)
    5. Page type (search_page, login_page, etc.)
    
    Return a JSON object with:
    {
      "is_general": true/false,
      "intent": "search/navigate/login/etc",
      "site": "amazon/google/github/etc",
      "parameters": {"query": "search term", "username": "user", "password": "pass"},
      "page_type": "search_page/login_page/etc",
      "actions": [...] // only for general commands
    }
    """
    
    try:
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nl_command}
            ],
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        try:
            interpretation = json.loads(content)
            return interpretation
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse AI response as valid JSON",
                "is_general": True,
                "actions": [{"type": "navigate", "url": "https://www.google.com"}]
            }
            
    except Exception as e:
        return {
            "error": f"Command interpretation error: {str(e)}",
            "is_general": True, 
            "actions": [{"type": "navigate", "url": "https://www.google.com"}]
        }

def generate_general_actions(interpretation: dict) -> dict:
    """
    Convert general command interpretation into browser actions
    """
    actions = []
    
    for action in interpretation["actions"]:
        if action["type"] == "navigate":
            actions.append(BrowserAction("navigate", url=action["url"]).to_dict())
        
        elif action["type"] == "input":
            actions.append(
                BrowserAction(
                    "input",
                    element_description=action["element"],
                    text=action["text"],
                    strategy="best_match"  # Uses smart element location
                ).to_dict()
            )
        
        elif action["type"] == "click":
            actions.append(
                BrowserAction(
                    "click",
                    element_description=action["element"],
                    strategy="best_match"
                ).to_dict()
            )
        
        elif action["type"] == "wait":
            actions.append(
                BrowserAction(
                    "wait",
                    timeout=action.get("timeout", 5000),
                    for_element=action.get("for_element")
                ).to_dict()
            )
    
    return {
        "actions": actions,
        "metadata": {
            "interpretation": interpretation,
            "strategy": "general_navigation"
        }
    }

def map_to_selectors(interpretation: dict) -> dict:
    """
    Map specific commands to hardcoded selectors (original functionality)
    """
    site = interpretation["site"]
    intent = interpretation["intent"]
    page_type = interpretation.get("page_type", intent)
    
    site_urls = {
        "amazon": "https://www.amazon.com",
        "google": "https://www.google.com",
        "github": "https://github.com"
        # Add more sites as needed
    }
    
    if site not in site_urls:
        return {"error": f"Unsupported site: {site}"}
    
    config = SITE_CONFIGS.get(f"{site}.com", {}).get(page_type)
    if not config:
        return {"error": f"Unsupported action for {site}"}
    
    actions = []
    
    # Enhanced action mapping
    if intent == "search":
        actions.extend([
            {
                "type": "navigate",
                "url": site_urls[site]
            },
            {
                "type": "input",
                "selector": config["actions"]["search_box"]["selector"],
                "fallbacks": config["actions"]["search_box"].get("fallbacks", []),
                "value": interpretation["parameters"]["query"]
            },
            {
                "type": "click",
                "selector": config["actions"]["search_button"]["selector"],
                "fallbacks": config["actions"]["search_button"].get("fallbacks", [])
            },
            {
                "type": "wait",
                "for_element": config.get("results_container", {}).get("selector"),
                "timeout": 5000
            }
        ])
    
    elif intent == "login":
        actions.extend([
            {
                "type": "navigate",
                "url": site_urls[site] + "/login"
            },
            {
                "type": "input",
                "selector": config["actions"]["username_field"]["selector"],
                "value": interpretation["parameters"]["username"]
            },
            {
                "type": "input",
                "selector": config["actions"]["password_field"]["selector"],
                "value": interpretation["parameters"]["password"]
            },
            {
                "type": "click",
                "selector": config["actions"]["login_button"]["selector"]
            },
            {
                "type": "verify",
                "selector": config["actions"]["login_success"]["selector"],
                "timeout": 3000
            }
        ])
    
    return {
        "actions": actions,
        "metadata": {
            "interpretation": interpretation,
            "selector_source": "hardcoded"
        }
    }