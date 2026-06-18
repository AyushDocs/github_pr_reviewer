import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import uvicorn
from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="PR Reviewer API", version="0.1.0")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
