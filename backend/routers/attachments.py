import os
import uuid
from pathlib import PurePosixPath
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

# Extension -> allowed content types
ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
}


def _clean_filename(raw: str | None) -> str:
    if not raw:
        return "file"
    name = PurePosixPath(raw).name
    if not name or name.startswith("."):
        return "file"
    return name[:255]


def _validate_file_type(filename: str, content_type: str | None) -> str:
    ext = os.path.splitext(filename)[1].lower()
    allowed_types = ALLOWED_EXTENSIONS.get(ext)
    if allowed_types is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is not allowed",
        )
    if content_type and content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{content_type}' does not match extension '{ext}'",
        )
    return ext


@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment(
    ticket_id: int,
    file: UploadFile,
    db: DbSession,
    user: CurrentUser,
):
    ticket = get_ticket_or_404(db, user, ticket_id)

    clean_name = _clean_filename(file.filename)
    ext = _validate_file_type(clean_name, file.content_type)

    contents = file.file.read()

    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5 MB limit",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = os.path.join(UPLOAD_DIR, stored_name)

    with open(storage_path, "wb") as f:
        f.write(contents)

    attachment = Attachment(
        ticket_id=ticket.id,
        uploader_id=user.id,
        filename=clean_name,
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