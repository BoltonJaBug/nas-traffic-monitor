from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.auth import authenticate_user, change_password, get_user_info

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    token = authenticate_user(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return LoginResponse(token=token)


@router.put("/password")
async def update_password(req: ChangePasswordRequest, username: str = get_current_user):
    ok = change_password(username, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="原密码错误")
    return {"message": "密码修改成功"}


@router.get("/info")
async def user_info(username: str = get_current_user):
    info = get_user_info(username)
    if not info:
        raise HTTPException(status_code=404, detail="用户不存在")
    return info
