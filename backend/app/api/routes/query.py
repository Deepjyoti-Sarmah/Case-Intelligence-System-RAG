import uuid
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.query import handle_query

router = APIRouter()

class QueryRequest(BaseModel):
    question: str
    options: dict | None = None

@router.post("/query")
async def query_endpoint(payload: QueryRequest, request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    result = handle_query(payload.question, request_id)
    return result
