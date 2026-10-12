import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from core.auth import get_current_user
from database import DbSession
from models import Attachment, User
from routers.tickets import get_ticket_or_404
from schemas.attachment import AttachmentRead

router = APIRouter(tags=["attachments"])

CurrentUser = Annotated[User, Depends(get_current_user)]

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
MAX_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
}


@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile,
    db: DbSession,
    user: CurrentUser,
):
    ticket = get_ticket_or_404(db, user, ticket_id)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file.content_type}' is not allowed",
        )

    contents = await file.read()

    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5 MB limit",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext = os.path.splitext(file.filename or "file")[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = os.path.join(UPLOAD_DIR, stored_name)

    with open(storage_path, "wb") as f:
        f.write(contents)

    attachment = Attachment(
        ticket_id=ticket.id,
        uploader_id=user.id,
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        size=len(contents),
        storage_path=stored_name,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get(
    "/tickets/{ticket_id}/attachments",
    response_model=list[AttachmentRead],
)
def list_attachments(
    ticket_id: int,
    db: DbSession,
    user: CurrentUser,
):
    ticket = get_ticket_or_404(db, user, ticket_id)

    attachments = db.scalars(
        select(Attachment)
        .where(Attachment.ticket_id == ticket.id)
        .order_by(Attachment.created_at)
    ).all()
    return list(attachments)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: DbSession,
    user: CurrentUser,
):
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # Org isolation through the ticket
    get_ticket_or_404(db, user, attachment.ticket_id)

    file_path = os.path.join(UPLOAD_DIR, attachment.storage_path)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
        )

    return FileResponse(
        path=file_path,
        filename=attachment.filename,
        media_type=attachment.content_type,
    )