"""
ابزارهای احراز هویت پنل وب:
  - هش کردن و بررسی پسورد (با passlib/bcrypt)
  - ساخت و بازکردن JWT (با python-jose)
  - dependency ای که روی endpoint های محافظت‌شده استفاده می‌شود
"""

import os
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import INTERNAL_API_KEY

# نکته‌ی امنیتی: این مقدار را در پروداکشن حتماً از طریق متغیر محیطی SECRET_KEY عوض کن
SECRET_KEY = os.environ.get("SECRET_KEY", "این-را-در-پروداکشن-عوض-کن")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # هر توکن یک روز اعتبار دارد

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# این شیء باعث می‌شود در صفحه‌ی /docs یک دکمه‌ی "Authorize" برای وارد کردن توکن دیده شود
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """پسورد خام را قبل از ذخیره در دیتابیس هش می‌کند."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """پسورد واردشده در فرم لاگین را با هشِ ذخیره‌شده مقایسه می‌کند."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """یک JWT امضاشده می‌سازد که شامل داده‌های ورودی + زمان انقضا است."""
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(credentials: HTTPAuthorizationCredentials) -> dict:
    """توکن را باز می‌کند؛ اگر نامعتبر یا منقضی‌شده بود خطای 401 می‌دهد."""
    try:
        return jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="توکن نامعتبر یا منقضی‌شده است",
        )


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """این dependency را روی همه‌ی endpoint های پنل وب (به‌جز ورود/setup) می‌گذاریم."""
    payload = _decode_token(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="این عملیات فقط برای ادمین مجاز است")
    return payload


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    """این dependency را روی مسیرهای /internal/* می‌گذاریم؛ فقط سرویس بات (با کلید مشترک) اجازه‌ی دسترسی دارد."""
    if not INTERNAL_API_KEY or x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی غیرمجاز")
