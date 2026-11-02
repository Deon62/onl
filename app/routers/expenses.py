"""Admin: Oryne's own operating expenses (registration, hosting, provider charges...)."""

import uuid
from datetime import date

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, select

from app.auth import AdminUser, FinanceWriter, Session
from app.errors import ApiError
from app.models import Expense
from app.schemas.common import Page
from app.schemas.platform import ExpenseIn, ExpenseOut
from app.services.audit import log_activity

router = APIRouter(prefix="/v1/admin/expenses", tags=["admin: expenses"])


def _label(e: Expense) -> str:
    return f"{e.description} (KES {e.amount_cents / 100:,.2f})"


@router.get("", response_model=Page[ExpenseOut])
async def list_expenses(
    _: AdminUser, session: Session,
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    q = select(Expense)
    if date_from:
        q = q.where(Expense.date >= date_from)
    if date_to:
        q = q.where(Expense.date <= date_to)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await session.execute(q.order_by(Expense.date.desc(), Expense.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return Page[ExpenseOut](items=[ExpenseOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(body: ExpenseIn, user: FinanceWriter, session: Session, request: Request):
    e = Expense(**body.model_dump(), created_by=user.email)
    session.add(e)
    log_activity(session, user=user, request=request, action="Recorded expense", target=_label(e))
    await session.commit()
    await session.refresh(e)
    return e


async def _get(session, expense_id: uuid.UUID) -> Expense:
    e = await session.get(Expense, expense_id)
    if e is None:
        raise ApiError(404, "not_found", "Expense not found.")
    return e


@router.put("/{expense_id}", response_model=ExpenseOut)
async def update_expense(expense_id: uuid.UUID, body: ExpenseIn, user: FinanceWriter, session: Session, request: Request):
    e = await _get(session, expense_id)
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    log_activity(session, user=user, request=request, action="Updated expense", target=_label(e))
    await session.commit()
    await session.refresh(e)
    return e


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: uuid.UUID, user: FinanceWriter, session: Session, request: Request):
    e = await _get(session, expense_id)
    log_activity(session, user=user, request=request, action="Deleted expense", target=_label(e))
    await session.delete(e)
    await session.commit()
