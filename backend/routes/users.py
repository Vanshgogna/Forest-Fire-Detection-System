from fastapi import APIRouter, Depends

from backend.core.security import Principal, get_current_principal, require_admin

router = APIRouter()


@router.get("/")
def list_users(_: Principal = Depends(require_admin)):
    return {"users": [{"id": 1, "email": "officer@firesight.ai", "full_name": "Forest Officer", "role": "forest_officer"}]}


@router.get("/me")
def get_me(principal: Principal = Depends(get_current_principal)):
    return {"email": principal.subject, "role": principal.role, "scopes": principal.scopes}
