from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.parser import parse_command
from services.browser import run_browser_task

router = APIRouter()

class CommandRequest(BaseModel):
    command: str

@router.post("/interact")
async def interact(request: CommandRequest):
    if not request.command:
        raise HTTPException(status_code=400, detail="Missing 'command'")
    
    parsed = await parse_command(request.command)
    if "error" in parsed:
        raise HTTPException(status_code=400, detail=parsed["error"])
    
    result = await run_browser_task(parsed)
    return result