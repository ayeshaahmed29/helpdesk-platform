from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.organization import Organization
from models.user import User, UserRole
from schemas.auth import SignupRequest, UserPublic
from security import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_TAKEN = "An account with this email already exists"


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()

    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    organization = Organization(name=payload.organization_name)
    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.owner,
        organization=organization,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)

    db.refresh(user)
    return user