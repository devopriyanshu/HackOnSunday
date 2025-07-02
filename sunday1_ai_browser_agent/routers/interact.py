from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from services.parser import parse_command
from services.browser import BrowserController
import json
import logging
import sys
import uuid

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class CommandRequest(BaseModel):
    command: str
    debug: bool = False
    headless: bool = False

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
    if not request.command:
        raise HTTPException(status_code=400, detail="Missing command")

    controller = None
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] 📥 Received command: {request.command}")

    try:
        parsed = await parse_command(request.command)
        logger.info(f"[{request_id}] 🧠 Parsed command object:\n%s", json.dumps(parsed, indent=2))

        if not parsed or not isinstance(parsed, dict) or "actions" not in parsed:
            raise HTTPException(status_code=400, detail="Invalid parsed command format")

        controller = BrowserController(headless=request.headless)
        logger.info(f"[{request_id}] 🚀 Starting browser with headless={request.headless}")
        results = await controller.execute_actions(parsed["actions"])

        response_data = {
            "command": request.command,
            "success": results["success"],
            "actions": [],
            "screenshots": results.get("screenshots", []),
            "final_url": None
        }

        try:
            if controller.page and not controller.page.is_closed():
                response_data["final_url"] = controller.page.url
        except Exception:
            pass

        for action_result in results.get("actions", []):
            response_data["actions"].append({
                "action": action_result.get("action", ""),
                "success": action_result.get("success", False),
                "details": action_result.get("details"),
                "screenshot": action_result.get("screenshot"),
                "error": action_result.get("error")
            })

        if request.debug:
            response_data["debug"] = {
                "parsed_command": parsed,
                "browser_state": {
                    "is_open": controller.browser is not None,
                    "page_ready": controller.page is not None
                }
            }

        logger.info(f"[{request_id}] ✅ Actions executed successfully")
        return ExecutionResult(**response_data)

    except Exception as e:
        logger.error(f"[{request_id}] ❌ Error processing command: {str(e)}", exc_info=True)
        debug_info = None
        if request.debug:
            debug_info = {
                "trace": repr(e),
                "parsed_command": parsed if "parsed" in locals() else None
            }
        return ExecutionResult(
            command=request.command,
            success=False,
            actions=[],
            screenshots=[],
            error=str(e),
            debug=debug_info
        )

    finally:
        if controller:
            try:
                await controller.close()
            except Exception as e:
                logger.error(f"[{request_id}] Error closing browser: {str(e)}")

@router.post("/actions", response_model=ExecutionResult)
async def execute_actions(request: DirectActionRequest):
    controller = None
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] 🛠️ Direct action request: %s", json.dumps(request.dict(), indent=2))

    try:
        controller = BrowserController(headless=request.headless)
        results = await controller.execute_actions(request.actions)

        response_data = {
            "command": "Direct action execution",
            "success": results["success"],
            "actions": results.get("actions", []),
            "screenshots": results.get("screenshots", []),
            "final_url": None
        }

        try:
            if controller.page and not controller.page.is_closed():
                response_data["final_url"] = controller.page.url
        except Exception:
            pass

        if request.debug:
            response_data["debug"] = {
                "browser_state": {
                    "is_open": controller.browser is not None,
                    "page_ready": controller.page is not None
                }
            }

        logger.info(f"[{request_id}] ✅ Direct actions executed successfully")
        return ExecutionResult(**response_data)

    except Exception as e:
        logger.error(f"[{request_id}] ❌ Error executing actions: {str(e)}", exc_info=True)
        return ExecutionResult(
            command="Direct action execution",
            success=False,
            actions=[],
            screenshots=[],
            error=str(e)
        )

    finally:
        if controller:
            try:
                await controller.close()
            except Exception as e:
                logger.error(f"[{request_id}] Error closing the browser: {str(e)}")
