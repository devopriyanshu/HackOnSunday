# interact.py - with fixed controller handling

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from services.parser import parse_command
from services.browser import BrowserController
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class CommandRequest(BaseModel):
    command: str
    debug: bool = False  # Optional debug flag
    headless: bool = False  # Option to run browser in headless mode

class ActionResponse(BaseModel):
    action: str
    success: bool
    details: Optional[Dict[str, Any]] = Field(default=None)
    screenshot: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)

class ExecutionResult(BaseModel):
    command: str
    success: bool
    actions: List[ActionResponse]
    screenshots: List[str] = Field(default_factory=list)
    final_url: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    debug: Optional[Dict[str, Any]] = Field(default=None)

class DirectActionRequest(BaseModel):
    actions: List[Dict]
    debug: bool = False
    headless: bool = False

@router.post("/interact", response_model=ExecutionResult)
async def interact(request: CommandRequest):
    """
    Execute a natural language browser command
    
    Parameters:
    - command: The natural language instruction
    - debug: If True, returns additional debug information
    - headless: If True, runs browser in headless mode
    
    Returns:
    - Detailed execution results including screenshots
    """
    if not request.command:
        raise HTTPException(status_code=400, detail="Missing command")
    
    controller = None
    try:
        # Step 1: Parse the natural language command
        parsed = await parse_command(request.command)
        if "error" in parsed:
            raise HTTPException(status_code=400, detail=parsed["error"])
        
        logger.info(f"Parsed actions: {parsed['actions']}")
        
        # Step 2: Execute the browser actions
        controller = BrowserController(headless=request.headless)
        results = await controller.execute_actions(parsed["actions"])
        
        # Build the response with proper null handling
        response_data = {
            "command": request.command,
            "success": results["success"],
            "actions": [],
            "screenshots": results.get("screenshots", []),
            "final_url": controller.page.url if controller.page and hasattr(controller.page, 'url') else None
        }
        
        # Transform actions to include all optional fields
        for action_result in results.get("actions", []):
            response_data["actions"].append({
                "action": action_result.get("action", ""),
                "success": action_result.get("success", False),
                "details": action_result.get("details"),
                "screenshot": action_result.get("screenshot"),
                "error": action_result.get("error")
            })
        
        # Include additional debug info if requested
        if request.debug:
            response_data["debug"] = {
                "parsed_command": parsed,
                "browser_state": {
                    "is_open": controller.browser is not None,
                    "page_ready": controller.page is not None
                }
            }
        
        # Validate against our model before returning
        return ExecutionResult(**response_data)
        
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}", exc_info=True)
        return ExecutionResult(
            command=request.command,
            success=False,
            actions=[],
            screenshots=[],
            error=str(e)
        )
    finally:
        # Ensure we always try to close the browser
        if controller:
            try:
                await controller.close()
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")

@router.post("/actions", response_model=ExecutionResult)
async def execute_actions(request: DirectActionRequest):
    """
    Directly execute a list of browser actions (for testing/debugging)
    """
    controller = None
    try:
        controller = BrowserController(headless=request.headless)
        results = await controller.execute_actions(request.actions)
        
        # Build response
        response_data = {
            "command": "Direct action execution",
            "success": results["success"],
            "actions": results.get("actions", []),
            "screenshots": results.get("screenshots", []),
            "final_url": controller.page.url if controller.page and hasattr(controller.page, 'url') else None
        }
        
        # Include debug info if requested
        if request.debug:
            response_data["debug"] = {
                "browser_state": {
                    "is_open": controller.browser is not None,
                    "page_ready": controller.page is not None
                }
            }
        
        return ExecutionResult(**response_data)
    except Exception as e:
        logger.error(f"Error executing actions: {str(e)}", exc_info=True)
        return ExecutionResult(
            command="Direct action execution",
            success=False,
            actions=[],
            screenshots=[],
            error=str(e)
        )
    finally:
        # Ensure we always try to close the browser
        if controller:
            try:
                await controller.close()
            except Exception as e:
                logger.error(f"Error closing the browser: {str(e)}")