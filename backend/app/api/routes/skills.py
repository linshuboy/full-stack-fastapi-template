import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from minio.error import S3Error
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.models import (
    Message,
    Skill,
    SkillCategory,
    SkillDownloadPublic,
    SkillPublic,
    SkillPublishUpdate,
    SkillsPublic,
    SkillUpdate,
)
from app.services.object_storage import (
    build_project_minio_url,
    build_skill_object_name,
    delete_skill_file,
    get_skill_download_url,
    upload_skill_file,
    validate_archive_contains_skill_md,
    validate_archive_filename,
)

router = APIRouter(prefix="/skills", tags=["skills"])


def _to_skill_public(skill: Skill, category_name: str) -> SkillPublic:
    return SkillPublic(
        id=skill.id,
        title=skill.title,
        description=skill.description,
        is_published=skill.is_published,
        category_id=skill.category_id,
        category_name=category_name,
        file_name=skill.file_name,
        archive_root_dir=skill.archive_root_dir,
        file_size=skill.file_size,
        file_content_type=skill.file_content_type,
        created_by_id=skill.created_by_id,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _get_skill_or_404(session: SessionDep, skill_id: uuid.UUID) -> Skill:
    skill = session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


def _get_category_or_404(session: SessionDep, category_id: uuid.UUID) -> SkillCategory:
    category = session.get(SkillCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def _ensure_unique_file_name(
    session: SessionDep, *, file_name: str, exclude_skill_id: uuid.UUID | None = None
) -> None:
    statement = select(Skill.id).where(
        func.lower(col(Skill.file_name)) == file_name.lower()
    )
    if exclude_skill_id:
        statement = statement.where(Skill.id != exclude_skill_id)
    existing_id = session.exec(statement).first()
    if existing_id:
        raise HTTPException(status_code=409, detail="Archive file name already exists")


def _resolve_request_scheme_host(request: Request) -> tuple[str, str]:
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return scheme, host


@router.get("/", response_model=SkillsPublic)
def read_skills(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    category_id: uuid.UUID | None = None,
    only_published: bool = True,
) -> Any:
    filters: list[Any] = []
    if not current_user.is_superuser:
        filters.append(Skill.is_published == True)  # noqa: E712
    elif only_published:
        filters.append(Skill.is_published == True)  # noqa: E712

    if category_id:
        filters.append(Skill.category_id == category_id)

    count_statement = select(func.count()).select_from(Skill)
    for clause in filters:
        count_statement = count_statement.where(clause)
    count = session.exec(count_statement).one()

    statement = (
        select(Skill).order_by(col(Skill.created_at).desc()).offset(skip).limit(limit)
    )
    for clause in filters:
        statement = statement.where(clause)
    skills = session.exec(statement).all()

    category_ids = {skill.category_id for skill in skills}
    categories = session.exec(
        select(SkillCategory).where(col(SkillCategory.id).in_(category_ids))
    ).all()
    category_map = {category.id: category.name for category in categories}

    data = [
        _to_skill_public(skill, category_map.get(skill.category_id, "Unknown"))
        for skill in skills
    ]
    return SkillsPublic(data=data, count=count)


@router.get("/{skill_id}", response_model=SkillPublic)
def read_skill(
    *, session: SessionDep, current_user: CurrentUser, skill_id: uuid.UUID
) -> SkillPublic:
    skill = _get_skill_or_404(session, skill_id)
    if not current_user.is_superuser and not skill.is_published:
        raise HTTPException(status_code=404, detail="Skill not found")
    category = _get_category_or_404(session, skill.category_id)
    return _to_skill_public(skill, category.name)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SkillPublic,
)
def create_skill(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form(max_length=1000)] = None,
    category_id: Annotated[uuid.UUID, Form()],
    is_published: Annotated[bool, Form()] = True,
    file: UploadFile = File(...),
) -> SkillPublic:
    category = _get_category_or_404(session, category_id)

    filename = validate_archive_filename(file.filename)
    _ensure_unique_file_name(session, file_name=filename)
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Archive file is empty")

    max_size = settings.SKILL_FILE_MAX_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Archive file exceeds {settings.SKILL_FILE_MAX_SIZE_MB}MB limit",
        )
    try:
        archive_root_dir = validate_archive_contains_skill_md(
            filename=filename, file_bytes=file_bytes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    skill_id = uuid.uuid4()
    object_name = build_skill_object_name(skill_id, filename)
    skill = Skill(
        id=skill_id,
        title=title,
        description=description,
        is_published=is_published,
        category_id=category_id,
        file_name=filename,
        archive_root_dir=archive_root_dir,
        file_object_name=object_name,
        file_size=len(file_bytes),
        file_content_type=file.content_type or "application/octet-stream",
        created_by_id=current_user.id,
    )

    try:
        upload_skill_file(
            object_name=object_name,
            file_bytes=file_bytes,
            content_type=skill.file_content_type or "application/octet-stream",
        )
    except (S3Error, ValueError):
        raise HTTPException(status_code=500, detail="Failed to upload archive file")

    session.add(skill)
    session.commit()
    session.refresh(skill)
    return _to_skill_public(skill, category.name)


@router.patch(
    "/{skill_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SkillPublic,
)
def update_skill(
    *,
    session: SessionDep,
    skill_id: uuid.UUID,
    skill_in: SkillUpdate,
) -> SkillPublic:
    skill = _get_skill_or_404(session, skill_id)

    if skill_in.category_id:
        _get_category_or_404(session, skill_in.category_id)

    update_data = skill_in.model_dump(exclude_unset=True)
    skill.sqlmodel_update(update_data)
    skill.updated_at = datetime.now(timezone.utc)
    session.add(skill)
    session.commit()
    session.refresh(skill)

    category = _get_category_or_404(session, skill.category_id)
    return _to_skill_public(skill, category.name)


@router.post(
    "/{skill_id}/file",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SkillPublic,
)
def replace_skill_file(
    *,
    session: SessionDep,
    skill_id: uuid.UUID,
    file: UploadFile = File(...),
) -> SkillPublic:
    skill = _get_skill_or_404(session, skill_id)
    category = _get_category_or_404(session, skill.category_id)

    filename = validate_archive_filename(file.filename)
    _ensure_unique_file_name(session, file_name=filename, exclude_skill_id=skill.id)
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Archive file is empty")

    max_size = settings.SKILL_FILE_MAX_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Archive file exceeds {settings.SKILL_FILE_MAX_SIZE_MB}MB limit",
        )
    try:
        archive_root_dir = validate_archive_contains_skill_md(
            filename=filename, file_bytes=file_bytes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    old_object_name = skill.file_object_name
    new_object_name = build_skill_object_name(skill.id, filename)
    try:
        upload_skill_file(
            object_name=new_object_name,
            file_bytes=file_bytes,
            content_type=file.content_type or "application/octet-stream",
        )
    except (S3Error, ValueError):
        raise HTTPException(status_code=500, detail="Failed to upload archive file")

    skill.file_name = filename
    skill.archive_root_dir = archive_root_dir
    skill.file_object_name = new_object_name
    skill.file_size = len(file_bytes)
    skill.file_content_type = file.content_type or "application/octet-stream"
    skill.updated_at = datetime.now(timezone.utc)
    session.add(skill)
    session.commit()
    session.refresh(skill)

    if old_object_name != new_object_name:
        try:
            delete_skill_file(old_object_name)
        except S3Error:
            # The new file is already persisted and DB state updated.
            pass

    return _to_skill_public(skill, category.name)


@router.patch(
    "/{skill_id}/publish",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SkillPublic,
)
def publish_skill(
    *,
    session: SessionDep,
    skill_id: uuid.UUID,
    body: SkillPublishUpdate,
) -> SkillPublic:
    skill = _get_skill_or_404(session, skill_id)
    skill.is_published = body.is_published
    skill.updated_at = datetime.now(timezone.utc)
    session.add(skill)
    session.commit()
    session.refresh(skill)
    category = _get_category_or_404(session, skill.category_id)
    return _to_skill_public(skill, category.name)


@router.get("/{skill_id}/download", response_model=SkillDownloadPublic)
def get_skill_download(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: Request,
    skill_id: uuid.UUID,
) -> SkillDownloadPublic:
    skill = _get_skill_or_404(session, skill_id)
    if not current_user.is_superuser and not skill.is_published:
        raise HTTPException(status_code=404, detail="Skill not found")
    try:
        minio_url = get_skill_download_url(skill.file_object_name)
    except S3Error:
        raise HTTPException(status_code=500, detail="Failed to generate download URL")
    scheme, host = _resolve_request_scheme_host(request)
    project_url = build_project_minio_url(
        presigned_url=minio_url,
        scheme=scheme,
        host=host,
    )
    return SkillDownloadPublic(
        url=project_url,
        expires_in=settings.SKILL_DOWNLOAD_URL_EXPIRE_SECONDS,
    )


@router.get("/{skill_id}/install-url", response_model=SkillDownloadPublic)
def get_skill_install_url(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: Request,
    skill_id: uuid.UUID,
) -> SkillDownloadPublic:
    skill = _get_skill_or_404(session, skill_id)
    if not current_user.is_superuser and not skill.is_published:
        raise HTTPException(status_code=404, detail="Skill not found")
    try:
        minio_url = get_skill_download_url(skill.file_object_name)
    except S3Error:
        raise HTTPException(status_code=500, detail="Failed to generate install URL")
    scheme, host = _resolve_request_scheme_host(request)
    project_url = build_project_minio_url(
        presigned_url=minio_url,
        scheme=scheme,
        host=host,
    )
    return SkillDownloadPublic(
        url=project_url,
        expires_in=settings.SKILL_DOWNLOAD_URL_EXPIRE_SECONDS,
    )


@router.delete(
    "/{skill_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_skill(*, session: SessionDep, skill_id: uuid.UUID) -> Message:
    skill = _get_skill_or_404(session, skill_id)
    object_name = skill.file_object_name

    session.delete(skill)
    session.commit()

    try:
        delete_skill_file(object_name)
    except S3Error:
        # DB deletion succeeded; object cleanup is best-effort.
        pass

    return Message(message="Skill deleted successfully")
