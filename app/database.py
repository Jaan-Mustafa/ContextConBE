import ssl as stdlib_ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _build_db_url(raw_url: str) -> tuple[str, dict]:
    parsed = urlparse(raw_url)
    params = parse_qs(parsed.query)
    connect_args: dict = {}

    sslmode = params.pop("sslmode", [None])[0]
    if sslmode and sslmode != "disable":
        ssl_ctx = stdlib_ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = stdlib_ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    if parsed.scheme in ("postgres", "postgresql", "postgresql+asyncpg"):
        scheme = "postgresql+asyncpg"
    else:
        scheme = parsed.scheme

    clean_query = urlencode(params, doseq=True)
    clean_url = urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))
    return clean_url, connect_args


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
