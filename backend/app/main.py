import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.config import ROOT_DIR, settings
from app.db.seekdb import db
from app.services.ingestion import import_files, import_samples
from app.services.powercontext import powercontext
from app.services.retrieval import audit, search


@asynccontextmanager
async def lifespan(_: FastAPI):
    await run_in_threadpool(db.initialize)
    yield


app = FastAPI(title="课程资料复习助手", version="0.1.0", lifespan=lifespan)
app.mount(
    "/static",
    StaticFiles(directory=ROOT_DIR / "frontend"),
    name="static",
)


class SearchRequest(BaseModel):
    user_id: str = Field(default="demo", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    query: str = Field(min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value


class UserRequest(BaseModel):
    user_id: str = Field(default="demo", pattern=r"^[A-Za-z0-9_-]{1,64}$")


def validate_user_id(user_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id):
        raise HTTPException(status_code=422, detail="invalid user_id")
    return user_id


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT_DIR / "frontend" / "index.html")


@app.get("/api/health")
def health():
    database = db.fetch_one("SELECT 1 AS value")
    context = powercontext.health()
    return {
        "status": "ready",
        "seekdb": database,
        "powercontext": context["status"],
        "embedding_model": settings.embedding_model,
    }


@app.post("/api/import")
async def import_uploads(
    user_id: str = Form(default="demo"),
    files: list[UploadFile] = File(...),
):
    validate_user_id(user_id)
    payloads = []
    for upload in files:
        data = await upload.read(settings.max_file_bytes + 1)
        payloads.append((upload.filename, data))
    outcomes = await run_in_threadpool(import_files, user_id, payloads)
    return {
        "outcomes": outcomes,
        "documents": db.list_documents(user_id),
    }


@app.post("/api/import-samples")
def import_sample_files(request: UserRequest):
    outcomes = import_samples(request.user_id)
    return {
        "outcomes": outcomes,
        "documents": db.list_documents(request.user_id),
    }


@app.get("/api/documents")
def documents(user_id: str = "demo"):
    validate_user_id(user_id)
    return {"documents": db.list_documents(user_id)}


@app.post("/api/search")
def search_materials(request: SearchRequest):
    weak_points = powercontext.list_weak_points(request.user_id)
    search_result = search(request.user_id, request.query, weak_points)
    powercontext.record_search(
        request.user_id,
        search_result["search_id"],
        request.query,
        search_result["results"],
    )
    topic = powercontext.update_topic(
        request.user_id,
        search_result["search_id"],
        request.query,
        search_result["results"],
    )
    return {**search_result, "topic": topic}


@app.get("/api/chunks/{chunk_id}")
def chunk_context(chunk_id: str, user_id: str = "demo"):
    validate_user_id(user_id)
    try:
        return db.get_context(chunk_id, user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="chunk not found") from exc


@app.get("/api/memory")
def memory(user_id: str = "demo"):
    validate_user_id(user_id)
    points = powercontext.list_weak_points(user_id)
    return {"weak_points": points}


@app.get("/api/review")
def review(user_id: str = "demo"):
    validate_user_id(user_id)
    points = powercontext.list_weak_points(user_id)
    for point in points:
        materials = db.get_chunks(point.get("chunk_ids", []), user_id)
        by_id = {item["chunk_id"]: item for item in materials}
        point["materials"] = [
            {
                **by_id[chunk_id],
                "source": next(
                    (
                        source["source"]
                        for source in point.get("sources", [])
                        if source["chunk_id"] == chunk_id
                    ),
                    by_id[chunk_id]["metadata"]["relative_path"],
                ),
            }
            for chunk_id in point.get("chunk_ids", [])
            if chunk_id in by_id
        ]
    return {"weak_points": points}


@app.get("/api/audit")
def audit_records(user_id: str = "demo"):
    validate_user_id(user_id)
    return audit(user_id)
