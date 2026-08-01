import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import admin, predictions, screener, screens, search, stocks, watchlist

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title="Stock Screener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)


app.include_router(screener.router)
app.include_router(screens.router)
app.include_router(search.router)
app.include_router(stocks.router)
app.include_router(predictions.router)
app.include_router(watchlist.router)
app.include_router(admin.router)
