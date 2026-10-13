from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from core.audit import AuditAction, log_audit_event
from core.permissions import MANAGER_ROLES, require_role
from database import DbSession
from models import Organization, User
from schemas.settings import SlaSettings, SlaSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

ManagerUser = Annotated[User, Depends(require_role(*MANAGER_ROLES))]


def _get_own_organization(db: DbSession, user: User) -> Organization:
    # the company always comes from the logged-in user, never from the request
    organization = db.get(Organization, user.organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return organization


@router.get("/sla", response_model=SlaSettings)
def get_sla(user: ManagerUser, db: DbSession):
    organization = _get_own_organization(db, user)
    return SlaSettings(first_reply_hours=organization.sla_first_response_hours)


@router.put("/sla", response_model=SlaSettings)
def update_sla(payload: SlaSettingsUpdate, user: ManagerUser, db: DbSession):
    organization = _get_own_organization(db, user)
    old_value = organization.sla_first_response_hours
    new_value = payload.first_reply_hours

    if new_value != old_value:
        organization.sla_first_response_hours = new_value
        log_audit_event(
            db,
            organization_id=organization.id,
            actor_user_id=user.id,
            action=AuditAction.settings_sla_updated,
            entity_type="organization",
            entity_id=organization.id,
            metadata={"first_reply_hours": [old_value, new_value]},
        )
        db.commit()

    return SlaSettings(first_reply_hours=new_value)