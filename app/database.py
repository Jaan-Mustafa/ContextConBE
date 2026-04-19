import re
import ssl as stdlib_ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _build_db_url(raw_url: str) -> tuple[str, dict]:
    connect_args: dict = {}

    has_ssl = bool(re.search(r"[?&](?:sslmode|ssl)=", raw_url))
    url = re.sub(r"[?&](?:sslmode|ssl)=[^&]*", "", raw_url)

    if has_ssl:
        ssl_ctx = stdlib_ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = stdlib_ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", url)

    return url, connect_args


_db_url, _connect_args = _build_db_url(settings.database_url)
engine = create_async_engine(
    _db_url,
    echo=settings.app_env == "development",
    connect_args=_connect_args,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
