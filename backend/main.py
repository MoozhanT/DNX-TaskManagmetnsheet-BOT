"""
بک‌اند «DNX Task Manager Bot»

  GET/POST     /api/tasks              -> لیست/ساخت تسک
  PATCH/DELETE /api/tasks/{id}         -> ویرایش/حذف تسک
  GET          /api/members            -> لیست اعضای تیم (برای انتخاب مسئول تسک)
  PATCH        /api/members/{id}       -> ویرایش عضو
  POST         /api/admin/setup        -> ساخت اولین حساب پنل وب (یک‌بارمصرف)
  POST         /api/admin/login        -> ورود پنل وب

بات تلگرام و scheduler یادآوری هم در همین پراسه، از طریق lifespan، اجرا می‌شوند.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import bot as bot_module
import models
import schemas
import scheduler as scheduler_module
from auth import create_access_token, hash_password, require_admin, verify_password
from database import Base, engine, get_db
from task_utils import apply_due_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(bot_module.start_polling())
    scheduler_module.start()
    yield
    scheduler_module.shutdown()
    bot_task.cancel()
    await bot_module.shutdown()


app = FastAPI(title="DNX Task Manager Bot — API", lifespan=lifespan)

# در حالت توسعه باز است؛ روی سرور واقعی به‌جای "*" آدرس دقیق فرانت را بگذار
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "message": "DNX Task Manager Bot backend روشن است ✅"}


# ═════════════════════════ احراز هویت پنل وب ═════════════════════════

@app.post("/api/admin/setup", response_model=schemas.Token)
def setup_admin(payload: schemas.AdminSetup, db: Session = Depends(get_db)):
    """endpoint یک‌بارمصرف: فقط وقتی هیچ حساب پنل‌وبی در دیتابیس نباشد کار می‌کند."""
    existing_admin = db.query(models.AdminUser).first()
    if existing_admin:
        raise HTTPException(status_code=403, detail="حساب ادمین قبلاً ساخته شده است")

    admin = models.AdminUser(username=payload.username, hashed_password=hash_password(payload.password))
    db.add(admin)
    db.commit()

    token = create_access_token({"sub": admin.username, "role": "admin"})
    return schemas.Token(access_token=token)


@app.post("/api/admin/login", response_model=schemas.Token)
def login_admin(payload: schemas.AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(models.AdminUser).filter(models.AdminUser.username == payload.username).first()
    if not admin or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")

    token = create_access_token({"sub": admin.username, "role": "admin"})
    return schemas.Token(access_token=token)


# ═════════════════════════ تسک‌ها (فقط ادمین پنل وب) ═════════════════════════

@app.get("/api/tasks", response_model=List[schemas.TaskOut], dependencies=[Depends(require_admin)])
def list_tasks(
    status: Optional[str] = None,
    assignee_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Task)
    if status:
        query = query.filter(models.Task.status == status)
    if assignee_id:
        query = query.filter(models.Task.assignee_id == assignee_id)
    return query.order_by(models.Task.created_at.desc()).all()


@app.post("/api/tasks", response_model=schemas.TaskOut, dependencies=[Depends(require_admin)])
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="عنوان تسک نمی‌تواند خالی باشد")

    if payload.assignee_id:
        assignee = db.query(models.Member).filter(models.Member.id == payload.assignee_id).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="عضو موردنظر پیدا نشد")

    task = models.Task(
        title=payload.title.strip(),
        description=payload.description,
        assignee_id=payload.assignee_id,
    )
    apply_due_date(task, payload.due_date)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}", response_model=schemas.TaskOut, dependencies=[Depends(require_admin)])
def update_task(task_id: str, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="تسک پیدا نشد")

    if payload.title is not None:
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="عنوان تسک نمی‌تواند خالی باشد")
        task.title = payload.title.strip()

    if payload.description is not None:
        task.description = payload.description

    if payload.assignee_id is not None:
        if payload.assignee_id:
            assignee = db.query(models.Member).filter(models.Member.id == payload.assignee_id).first()
            if not assignee:
                raise HTTPException(status_code=404, detail="عضو موردنظر پیدا نشد")
        task.assignee_id = payload.assignee_id or None

    if "due_date" in payload.model_fields_set:
        apply_due_date(task, payload.due_date)

    if payload.status is not None:
        if payload.status not in ("pending", "done"):
            raise HTTPException(status_code=400, detail="وضعیت نامعتبر است (باید pending یا done باشد)")
        task.status = payload.status
        task.completed_at = datetime.utcnow() if payload.status == "done" else None

    db.commit()
    db.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", dependencies=[Depends(require_admin)])
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="تسک پیدا نشد")
    db.delete(task)
    db.commit()
    return {"deleted": True, "id": task_id}


# ═════════════════════════ اعضای تیم (فقط ادمین پنل وب) ═════════════════════════

@app.get("/api/members", response_model=List[schemas.MemberOut], dependencies=[Depends(require_admin)])
def list_members(db: Session = Depends(get_db)):
    return db.query(models.Member).order_by(models.Member.full_name).all()


@app.patch("/api/members/{member_id}", response_model=schemas.MemberOut, dependencies=[Depends(require_admin)])
def update_member(member_id: str, payload: schemas.MemberUpdate, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="عضو پیدا نشد")

    if payload.full_name is not None:
        if not payload.full_name.strip():
            raise HTTPException(status_code=400, detail="نام نمی‌تواند خالی باشد")
        member.full_name = payload.full_name.strip()

    if payload.is_admin_bot is not None:
        member.is_admin_bot = payload.is_admin_bot

    db.commit()
    db.refresh(member)
    return member
