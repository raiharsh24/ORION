import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_api_key, compute_api_token, verify_api_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    scope: str = "default"
    expiry: int = 3600


class TokenResponse(BaseModel):
    token: str
    scope: str
    expires_in: int


class VerifyRequest(BaseModel):
    token: str
    scope: str


class VerifyResponse(BaseModel):
    valid: bool


@router.post("/token", response_model=TokenResponse)
async def issue_token(req: TokenRequest, api_key: str = Depends(get_api_key)):
    token = compute_api_token(req.scope, req.expiry)
    return TokenResponse(token=token, scope=req.scope, expires_in=req.expiry)


@router.post("/verify", response_model=VerifyResponse)
async def verify_token(req: VerifyRequest):
    valid = verify_api_token(req.token, req.scope)
    return VerifyResponse(valid=valid)
