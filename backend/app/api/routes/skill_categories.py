import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import (
    Message,
    Skill,
    SkillCategoriesPublic,
    SkillCategory,
    SkillCategoryCreate,
    SkillCategoryPublic,
    SkillCategoryUpdate,
)

router = APIRouter(prefix="/skill-categories", tags=["skill-categories"])


@router.get("/", response_model=SkillCategoriesPublic)
def read_skill_categories(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
) -> Any:
    filters: list[Any] = []
    if not current_user.is_superuser or not include_inactive:
        filters.append(SkillCategory.is_active == True)  # noqa: E712

    count_statement = select(func.count()).select_from(SkillCategory)
    for clause in filters:
        count_statement = count_statement.where(clause)
    count = session.exec(count_statement).one()

    statement = (
        select(SkillCategory)
        .order_by(col(SkillCategory.sort_order), col(SkillCategory.name))
        .offset(skip)
        .limit(limit)
    )
    for clause in filters:
        statement = statement.where(clause)
    categories = session.exec(statement).all()
    return SkillCategoriesPublic(data=categories, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SkillCategoryPublic,
)
def create_skill_category(
    *, session: SessionDep, category_in: SkillCategoryCreate
) -> SkillCategory:
    existing = session.exec(
        select(SkillCategory).where(SkillCategory.name == category_in.name)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category name already exists")
    category = SkillCategory.model_validate(category_in)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.patch(
    "/{category_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SkillCategoryPublic,
)
def update_skill_category(
    *,
    session: SessionDep,
    category_id: uuid.UUID,
    category_in: SkillCategoryUpdate,
) -> SkillCategory:
    category = session.get(SkillCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category_in.name and category_in.name != category.name:
        existing = session.exec(
            select(SkillCategory).where(SkillCategory.name == category_in.name)
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Category name already exists")

    update_data = category_in.model_dump(exclude_unset=True)
    category.sqlmodel_update(update_data)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete(
    "/{category_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_skill_category(*, session: SessionDep, category_id: uuid.UUID) -> Message:
    category = session.get(SkillCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    skills_count = session.exec(
        select(func.count()).select_from(Skill).where(Skill.category_id == category_id)
    ).one()
    if skills_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with existing skills",
        )

    session.delete(category)
    session.commit()
    return Message(message="Category deleted successfully")
