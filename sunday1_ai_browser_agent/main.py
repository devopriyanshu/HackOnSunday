from fastapi import FastAPI
from routers.interact import router as interact_router

app = FastAPI(
    title="AI Browser Agent",
    description="Natural language to browser automation",
    version="1.0"
)

app.include_router(interact_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)