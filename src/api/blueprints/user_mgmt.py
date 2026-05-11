import os
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import get_current_user

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ADMIN_EMAILS: set[str] = set(
    e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
)


def _get_supabase_admin():
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase admin not configured.")
    return create_client(url, key)


def _user_exists(email: str) -> bool:
    try:
        supa = _get_supabase_admin()
        users = supa.auth.admin.list_users()
        return any(u.email and u.email.lower() == email.lower() for u in (users or []))
    except Exception:
        return False


async def get_admin_user(user_id: str = Depends(get_current_user)) -> str:
    supa = _get_supabase_admin()
    res = supa.auth.admin.get_user_by_id(user_id)
    email = res.user.email if res.user else ""
    if email.lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user_id


class InviteRequest(BaseModel):
    email: str


user_mgmt_router = APIRouter()


@user_mgmt_router.get("/api/admin/users")
async def list_users(_: str = Depends(get_admin_user)):
    supa = _get_supabase_admin()
    res = supa.auth.admin.list_users()
    return {"users": [
        {
            "id": u.id,
            "email": u.email,
            "created_at": u.created_at,
            "last_sign_in_at": u.last_sign_in_at,
        }
        for u in (res or [])
    ]}


@user_mgmt_router.post("/api/admin/users/invite")
async def invite_user(body: InviteRequest, _: str = Depends(get_admin_user)):
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(status_code=422, detail="Invalid email address.")
    supa = _get_supabase_admin()
    try:
        supa.auth.admin.invite_user_by_email(body.email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": f"Invite sent to {body.email}"}


@user_mgmt_router.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: str, _: str = Depends(get_admin_user)):
    supa = _get_supabase_admin()
    try:
        supa.auth.admin.delete_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "User deleted."}
