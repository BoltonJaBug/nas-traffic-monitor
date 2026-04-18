from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.database import db
from app.notifier import get_webhook_url, set_webhook_url, test_webhook

router = APIRouter(prefix="/api/settings", tags=["settings"])


class WebhookConfig(BaseModel):
    url: str


@router.get("/webhook")
async def get_webhook(_user: str = Depends(get_current_user)):
    return {"url": get_webhook_url()}


@router.put("/webhook")
async def update_webhook(cfg: WebhookConfig, _user: str = Depends(get_current_user)):
    set_webhook_url(cfg.url)
    return {"message": "Webhook 地址已更新"}


@router.post("/webhook/test")
async def test_webhook_endpoint(cfg: WebhookConfig, _user: str = Depends(get_current_user)):
    ok, msg = test_webhook(cfg.url)
    return {"success": ok, "message": msg}
