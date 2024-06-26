import time
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_pagination import add_pagination
from fastapi_pagination.utils import disable_installed_extensions_check
from prometheus_fastapi_instrumentator import Instrumentator
from redis import asyncio as aioredis
from sqladmin import Admin

from admin.admin import authentication_backend
from admin.models_admin import CommentAdmin, PostAdmin, UserAdmin
from config.config import settings
from database.database import engine
from logger import logger
from middleware.middleware import RateLimitingMiddleware
from routers.auth_router import router as router_auth
from routers.like_router import router as router_like
from routers.posts_router import router as router_posts
from routers.test_prometheus import router as router_prometheus
from routers.users_router import router as router_users

sentry_sdk.init(
    dsn=settings.DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)


disable_installed_extensions_check()




@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = aioredis.from_url(
        f"redis://{settings.REDIS_HOST}", encoding="utf-8", decode_respone=True
    )
    FastAPICache.init(RedisBackend(redis), prefix="cache")
    print("Start app")
    yield
    print("Close app")


app = FastAPI(
    title="CRUD",
    lifespan=lifespan,
    swagger_ui_parameters={"operationsSorter": "method"},
)


app.mount("/static", StaticFiles(directory="static"), "static")

add_pagination(app)

admin = Admin(
    app,
    engine,
    authentication_backend=authentication_backend,
    templates_dir="temp",
)

app.add_middleware(RateLimitingMiddleware)

admin.add_view(UserAdmin)
admin.add_view(PostAdmin)
admin.add_view(CommentAdmin)


app.include_router(router_users)
app.include_router(router_posts)
app.include_router(router_auth)
app.include_router(router_like)
app.include_router(router_prometheus)



origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PUT", "PUTCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_proccess_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    proccess_time = time.time() - start_time
    response.headers["X-Proccess-Time"] = str(proccess_time)
    logger.info(
        "Request execution time",
        extra={"proccess_time": round(proccess_time, 3)},
    )
    return response

instrumentator = Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=[".*admin.*", "/metrics"],
)
instrumentator.instrument(app).expose(app)