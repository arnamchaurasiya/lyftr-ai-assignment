from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Any
from scraper import scrape

app = FastAPI()
templates = Jinja2Templates(directory="templates")


class ScrapeRequest(BaseModel):
    url: str


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/scrape")
def scrape_api(req: ScrapeRequest):
    if not req.url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    return scrape(req.url)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
