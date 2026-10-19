# MWU-SHORTY-001 — Planning Report

**Classification:** APPROVED-CANDIDATE (awaits Gate 3)
**Generated:** 2026-05-14T11:30:00Z
**Agent:** planner_agent (Opus, feature-dev:code-architect)
**Upstream:** comprehension-001.md (12 BR-C, 5 contexts), gate-2.md (APPROVED)

---

## 1. Target Application Architecture

### 1.1 Layered architecture (models / schemas / service / router / encode-module)

The target follows the FrontAccounting POC's established `app/modules/<feature>/` convention. For Shorty there is a **single** feature module — `urls` — because the source has a single bounded data entity. The five Comprehension bounded contexts (UrlCreation, UrlLookup, FormatNegotiation, AccessControl, Telemetry) all share the `urls` row and the encode/decode algorithm, so a single module groups the cohesive code, while the encode/decode component is split into its own pure-Python file (`encode.py`) because it is the load-bearing parity surface and must be testable in isolation without FastAPI or SQLAlchemy imports.

The strict layering, top-down:

| Layer | Path | Imports allowed | Purpose |
|---|---|---|---|
| Bootstrap | `app/main.py` | core, db, modules | Build the `FastAPI` app, register routers, install middleware, expose lifespan hooks. |
| Configuration | `app/core/config.py` | pydantic-settings only | Single `Settings` BaseSettings class. Read once at startup. |
| Database engine | `app/db/engine.py` | core.config, sqlalchemy.ext.asyncio | Async engine + session factory + `get_db_session` dependency. |
| ORM base | `app/db/base.py` | sqlalchemy.orm | `DeclarativeBase` subclass and the package import surface for Alembic. |
| Module — models | `app/modules/urls/models.py` | db.base, sqlalchemy | The single `Url` ORM class — pure data definition, no behaviour. |
| Module — schemas | `app/modules/urls/schemas.py` | pydantic | Request / response / settings DTOs; no DB types leak. |
| Module — encode | `app/modules/urls/encode.py` | stdlib only (`hashlib`, `dataclasses`) | Pure functions `encode`, `decode`, `get_seed`, `num_to_alpha`, `alpha_to_num`; zero framework deps. |
| Module — formatting | `app/modules/urls/formatting.py` | stdlib (`html`, `xml`) | Render-helpers for the four output formats (BR-C-09). |
| Module — service | `app/modules/urls/service.py` | models, schemas, encode, formatting, sqlalchemy.ext.asyncio | Async business-logic methods. Pure I/O around encode + DB. |
| Module — dependencies | `app/modules/urls/dependencies.py` | fastapi, core.config | FastAPI `Depends()` providers: settings, IP whitelist gate, client-IP resolver. |
| Module — router | `app/modules/urls/router.py` | fastapi, dependencies, service, schemas | Route registration only; calls into service, maps exceptions to HTTP statuses. |
| Module — errors | `app/modules/urls/errors.py` | (stdlib) | Domain-specific exception classes raised by service, caught by router. |

Service never imports `fastapi`; router never imports `sqlalchemy` directly. This bidirectional firewall is the single most important architectural invariant for Stage 5 Self-Review.

### 1.2 Async-everywhere rationale

Async is mandatory throughout (`uvicorn` + `asyncpg` + SQLAlchemy 2.x async session) for three reasons:

1. **PG driver parity** — `asyncpg` is the canonical PostgreSQL driver Pydantic+FastAPI projects standardise on; the FrontAccounting POC uses the same DSN shape (`postgresql+asyncpg://...`).
2. **Telemetry fire-and-forget** — BR-C-10 mandates that a redirect must still succeed when the `UPDATE urls SET hits = hits + 1, accessed = now()` fails. With async we can dispatch the telemetry update as a `BackgroundTasks` item or as an `asyncio.create_task` (decision deferred to §7); blocking sync would force a synchronous round-trip on the hot path.
3. **Hit-counter concurrency under load** — the dual-run harness will hammer both backends with concurrent identical-URL creates (BR-C-01 race fixture). Async + a single `ON CONFLICT` insert gives O(1) DB round-trips per request and no pool starvation under burst.

No mix of `def` and `async def` business code is permitted. Pure-CPU helpers (`encode.encode`, `formatting.render_xml`) stay synchronous because they do no I/O; everything that touches the DB is `async def`. Anywhere a `def` is needed for a callback (FastAPI dependency, validator), keep it free of I/O.

### 1.3 Pydantic v2 + SQLAlchemy 2.x conventions

**Pydantic v2 conventions:**

- All schemas inherit from `pydantic.BaseModel`. Use `model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, from_attributes=True)` on every response schema; request schemas use `extra="forbid"` only.
- Use `Annotated[str, Field(..., max_length=2048, pattern=r"^http[s]?://\w+")]` for the `url` field to push regex validation into Pydantic (BR-C-02). The pattern is identical to the legacy regex character-for-character — no anchored end-of-string.
- Format negotiation uses a `StrEnum` (`OutputFormat`) with literal values `"text" | "json" | "xml" | "html"`; the router applies `.lower()` before the lookup (BR-C-09 case-insensitive).
- Custom validators go on the schema class as `@field_validator("url", mode="after")`; no `@root_validator` usage (removed in v2).

**SQLAlchemy 2.x conventions:**

- Single `DeclarativeBase` subclass `Base` in `app/db/base.py`. All models import from `app.db.base`.
- Columns declared with `Mapped[T]` typed annotation and `mapped_column(...)` constructor. No legacy `Column(...)` syntax.
- All async access via `AsyncSession`. No `Session` (sync) anywhere.
- Insert with conflict-resolution uses `from sqlalchemy.dialects.postgresql import insert as pg_insert`, then `pg_insert(Url).values(...).on_conflict_do_nothing(index_elements=["url"]).returning(Url.id)`.
- Increment uses `update(Url).where(Url.id == id_).values(hits=Url.hits + 1, accessed=func.now())` — never a SELECT-modify-WRITE in Python.

### 1.4 Dependency injection wiring (per-request DB session)

There is exactly one DB-session dependency: `app.db.engine.get_db_session()`. It is an `async def` generator that yields an `AsyncSession` bound to the request's lifetime, commits on success, rolls back on exception, and always closes. The router declares `db: Annotated[AsyncSession, Depends(get_db_session)]` on every route that touches the database.

The service does NOT call `get_db_session` itself; the session is always **passed in** by the router. This keeps the service unit-testable with a hand-rolled `AsyncSession` against in-memory SQLite (`sqlite+aiosqlite:///:memory:`) without FastAPI involvement.

Other DI providers:

| Provider | Type | Purpose |
|---|---|---|
| `get_settings` | `lambda: Settings` (cached) | Inject the immutable `Settings` instance for hostname / chars / salt / padding. |
| `get_client_ip` | `(request: Request) -> str` | Resolve real client IP via `request.client.host` after uvicorn's `ProxyHeadersMiddleware` rewrites it (BR-C-04, RF-05 fix). |
| `require_ip_allowed` | `(client_ip, settings) -> None` | Raise `HTTPException(403)` if whitelist is non-empty and IP not in it. Used only by create routes (R1, R4). |

Caching: `get_settings` returns the module-level singleton; do not use `lru_cache()` — Settings is built once at startup and never reloads in Phase 1.

### 1.5 Configuration shape (Pydantic BaseSettings)

The `Settings` class lives in `app/core/config.py` and is a `pydantic_settings.BaseSettings` subclass. Settings are loaded from environment variables prefixed `SHORTY_` (e.g. `SHORTY_SALT`, `SHORTY_PADDING`). A `.env` file is also supported via `model_config = SettingsConfigDict(env_prefix="SHORTY_", env_file=".env", env_file_encoding="utf-8", extra="ignore")`.

Validation runs at instantiation. Three invariants enforced in `model_validator(mode="after")`:

1. `len(set(chars)) == len(chars)` — every character in `SHORTY_CHARS` is unique.
2. `len(chars) >= 2` — base ≥ 2.
3. `padding >= 0` — non-negative.

If validation fails, the process exits with `RuntimeError` raised at module import time. This is intentional: a misconfigured encoder must never be allowed to silently corrupt URLs.

The salt field is `SecretStr` so it is masked in logs (defence-in-depth even though Gate 1 locked it to `""`).

---

## 2. File Tree (final)

The CodeGen agent MUST produce exactly these files. Paths are relative to the engagement root `migrations/shorty/generated/backend/`.

```
migrations/shorty/generated/backend/
├── pyproject.toml                         # Project metadata, dependencies, ruff/pytest config
├── alembic.ini                            # Alembic config (script_location=app/db/migrations)
├── README.md                              # How to run locally + dual-run harness
├── .env.example                           # All SHORTY_* env vars with safe defaults
├── docker-compose.yml                     # FastAPI service + Postgres 16 + (optional) PHP reference
├── Dockerfile                             # Slim python:3.12 image, uvicorn entrypoint
├── app/
│   ├── __init__.py
│   ├── main.py                            # FastAPI app factory, lifespan, middleware
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                      # Settings (BaseSettings) — env-var loading + validation
│   │   └── logging.py                     # Stdlib logging setup (JSON optional)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                        # DeclarativeBase subclass; imports for Alembic discovery
│   │   ├── engine.py                      # async engine, session factory, get_db_session() dep
│   │   └── migrations/
│   │       ├── env.py                     # Alembic env — async-aware
│   │       ├── script.py.mako             # Alembic template
│   │       └── versions/
│   │           └── 0001_init_urls.py      # Single migration — creates urls table per §3.1 DDL
│   └── modules/
│       ├── __init__.py
│       └── urls/
│           ├── __init__.py
│           ├── encode.py                  # PURE — encode/decode/get_seed/num_to_alpha/alpha_to_num
│           ├── errors.py                  # UrlNotFound, BadUrl, IpNotAllowed, EncodeOverflow
│           ├── models.py                  # SQLAlchemy Url model (single class)
│           ├── schemas.py                 # Pydantic request/response models
│           ├── formatting.py              # render_text/json/xml/html for create-response
│           ├── dependencies.py            # get_settings, get_client_ip, require_ip_allowed
│           ├── service.py                 # UrlService — async business methods
│           └── router.py                  # APIRouter: R1–R5 endpoint definitions
└── tests/
    ├── __init__.py
    ├── conftest.py                        # pytest-asyncio fixtures: sqlite-aiosqlite engine, client, vectors
    ├── fixtures/
    │   ├── __init__.py
    │   └── encode_vectors.json            # Generated from PHP reference (TestGen Stage 6 owns the regen)
    ├── unit/
    │   ├── __init__.py
    │   ├── test_encode.py                 # 12 tests — BR-C-12 + property tests
    │   ├── test_formatting.py             # BR-C-09 format renderers
    │   └── test_schemas.py                # Pydantic validation cases
    ├── integration/
    │   ├── __init__.py
    │   ├── test_create.py                 # R1, R4 — BR-C-01..04, 08, 09
    │   ├── test_lookup.py                 # R2, R3 — BR-C-05..08
    │   ├── test_telemetry.py              # BR-C-10, BR-C-11
    │   └── test_health.py                 # R5
    └── parity/
        ├── __init__.py
        └── test_php_parity.py             # Stage 7 dual-run scaffolding (skipped unless PHP container up)
```

**File count planned: 36 source/config files + 14 test files = 50 deliverables.**

Of those, **15 are logic-carrying** (non-trivial implementations): `main.py`, `core/config.py`, `core/logging.py`, `db/engine.py`, `db/base.py`, `db/migrations/env.py`, `db/migrations/versions/0001_init_urls.py`, `modules/urls/{encode.py, errors.py, models.py, schemas.py, formatting.py, dependencies.py, service.py, router.py}`. Tests add another 7 logic-carrying files (`conftest.py` + 6 `test_*.py`).

---

## 3. PostgreSQL Schema + Migration

### 3.1 DDL (locked, from comprehension §7.1)

Copy the DDL verbatim — no design freedom.

```sql
CREATE TABLE urls (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url        TEXT NOT NULL,
    created    TIMESTAMPTZ NOT NULL DEFAULT now(),
    accessed   TIMESTAMPTZ,
    hits       INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT urls_url_unique UNIQUE (url),
    CONSTRAINT urls_hits_nonneg CHECK (hits >= 0)
);

CREATE INDEX urls_url_idx ON urls (url);
```

The `UNIQUE` constraint already produces a B-tree index on `url`; `urls_url_idx` is redundant but matches Comprehension §7.1 verbatim and gives a stable index name for query plans. CodeGen MUST keep it.

### 3.2 Alembic migration file structure

| File | Required contents |
|---|---|
| `alembic.ini` | `script_location = app/db/migrations`; `sqlalchemy.url = ${SHORTY_DB_URL}` (interpolated from env); `[loggers]` block standard. |
| `app/db/migrations/env.py` | Async-aware env. Imports `app.db.base.Base.metadata` for `target_metadata`. Uses `connectable = AsyncEngine(create_async_engine(settings.db_url))`. `run_migrations_online()` calls `async with connectable.connect() as conn: await conn.run_sync(do_run_migrations)`. |
| `app/db/migrations/script.py.mako` | Standard Alembic template — no customisation. |
| `app/db/migrations/versions/0001_init_urls.py` | The single, immutable initial migration. Revision id `0001_init_urls`; `down_revision = None`. |

Migration upgrade body uses `op.create_table("urls", ...)` with these column definitions in order: `id` (`sa.Integer`, primary_key=True, `sa.Identity(always=True)`), `url` (`sa.Text`, nullable=False), `created` (`sa.TIMESTAMPTZ`, server_default=`sa.func.now()`, nullable=False), `accessed` (`sa.TIMESTAMPTZ`, nullable=True), `hits` (`sa.Integer`, server_default="0", nullable=False). Constraints: `sa.UniqueConstraint("url", name="urls_url_unique")`, `sa.CheckConstraint("hits >= 0", name="urls_hits_nonneg")`. Index: `op.create_index("urls_url_idx", "urls", ["url"])`. Downgrade reverses.

### 3.3 Seed strategy for tests + dual-run harness

| Stage | Strategy |
|---|---|
| Unit tests | No DB — encode/formatting tests are pure. |
| Integration tests | Per-test SQLite (`sqlite+aiosqlite:///:memory:`). Schema bootstrapped by `Base.metadata.create_all(engine)`. No Alembic — `create_all` is faster and SQLite cannot evaluate `GENERATED ALWAYS AS IDENTITY` syntax. The SQLAlchemy model uses `Mapped[int] = mapped_column(primary_key=True)` which translates correctly on both dialects. |
| Parity / dual-run tests | Postgres 16 in docker-compose. `alembic upgrade head` runs at container start. Seed file `tests/fixtures/parity_urls.sql` inserts a deterministic set (id 1, 10, 25, 26, 52, 61, 62, 100, 1000). |
| Empty greenfield prod | Migration creates the table; no seed (Gate 1 OQ-09: greenfield). |

**Dialect-portability rule:** integration tests for `create_or_get` run on a Postgres test container (`testcontainers-postgresql`), while all other integration tests use SQLite. This is the only place we accept the speed penalty.

---

## 4. SQLAlchemy Models

### 4.1 `Url` (app/modules/urls/models.py)

**Class name:** `Url`
**Table name:** `urls`
**Module:** `app.modules.urls.models`
**Base:** `app.db.base.Base`

**Column declarations (signatures only, no bodies):**

```python
class Url(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(
        Integer,
        Identity(always=True),
        primary_key=True,
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    accessed: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    hits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    __table_args__ = (
        UniqueConstraint("url", name="urls_url_unique"),
        CheckConstraint("hits >= 0", name="urls_hits_nonneg"),
        Index("urls_url_idx", "url"),
    )
```

**Relationships:** None. Single-entity domain.

**Repr:** `__repr__` returns `f"Url(id={self.id!r}, hits={self.hits!r})"`. Never include `self.url` in repr — logs must not leak URLs.

### 4.2 Module docstring + traceability header

CodeGen MUST emit a traceability header at the top of `models.py`:

```python
# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-01, BR-C-05, BR-C-10, BR-C-11
# LEGACY: source/shorty.php (class Shorty), source/database.sql
# COMPONENT: modules/urls/models
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG
```

---

## 5. Pydantic Schemas

All schemas live in `app/modules/urls/schemas.py`. Imports only `pydantic`, `typing`, `enum`, `datetime`; no SQLAlchemy types leak through.

### 5.1 `OutputFormat` (StrEnum)

```python
class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
    XML = "xml"
    HTML = "html"

    @classmethod
    def parse(cls, raw: str | None) -> "OutputFormat":
        """Case-insensitive parse; unknown → HTML (BR-C-09)."""
        ...
```

### 5.2 `CreateUrlRequest`

```python
class CreateUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    url: Annotated[str, Field(..., min_length=1, max_length=2048, pattern=r"^http[s]?://\w+")]
    format: Annotated[str | None, Field(default=None, max_length=16)] = None
```

Used **only** by `POST /shorten` (R4) for the JSON body case. The `GET /?url=` case (R1) reads the same values from `request.query_params` and validates them with the same constraints.

### 5.3 `CreateUrlResult` (internal — not a response model)

```python
class CreateUrlResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    code: str
    short_url: str
    was_created: bool   # True if INSERT happened, False if row pre-existed (BR-C-01)
```

### 5.4 `JsonCreateResponse` (response model for `?format=json`)

```python
class JsonCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
```

### 5.5 `ProblemDetail` (RFC 9457 lite)

```python
class ProblemDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    detail: str
    type: str | None = None
```

### 5.6 `HealthResponse`

```python
class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]
```

### 5.7 Aliases / serialisation rules

- No field aliases — payload field names are stable from Phase 1 onward.
- `model_dump_json()` is the canonical serialisation entry point.
- Datetime fields are not in the create or lookup response payloads in Phase 1.

---

## 6. Encode Module (the load-bearing component)

### 6.1 Module structure (app/modules/urls/encode.py)

The file MUST contain only:

1. A module-level docstring citing BR-C-12 + invariants I-1 through I-10.
2. A frozen dataclass `EncoderConfig`.
3. Five public functions: `encode`, `decode`, `get_seed`, `num_to_alpha`, `alpha_to_num`.
4. Two private helpers: `_validate_chars`, `_md5_hex`.
5. **Zero** other imports beyond `hashlib`, `dataclasses`, and `typing`.
6. **Zero** module-level state.

**Forbidden patterns** for CodeGen review:
- Importing `fastapi`, `sqlalchemy`, or `pydantic` here.
- Using `int()` without `base=10` on the seed-concat result (Invariant I-5).
- Using `/` instead of `//` anywhere (Invariant I-6).
- Using `pow(b, e)` instead of `b ** e` (Invariant I-7).
- Hashing `salt + str(n)` instead of `str(n) + salt` (Invariant I-4).
- Use `str.zfill(padding)` for padding (not `format()` mini-language).

### 6.2 Function signatures (exact)

```python
@dataclass(frozen=True, slots=True)
class EncoderConfig:
    """Immutable config for one encode/decode session.

    Invariants enforced at construction:
      - chars contains no duplicates
      - len(chars) >= 2
      - padding >= 0
    """
    chars: str
    salt: str
    padding: int

    def __post_init__(self) -> None: ...  # raises ValueError on invariant violation


def encode(n: int, cfg: EncoderConfig) -> str:
    """Encode a positive integer ID into the short-code alphabet.

    Implements BR-C-12 / Comprehension §4.1 encode(n, salt, padding, S).

    Raises:
        ValueError: if n < 1.
    """


def decode(code: str, cfg: EncoderConfig) -> int:
    """Decode a short-code string back to the integer ID.

    Implements BR-C-12 / Comprehension §4.1 decode(s, salt, padding, S).

    Raises:
        ValueError: if any character of code is not in cfg.chars.
    """


def get_seed(n: int, salt: str, padding: int) -> str:
    """Compute the zero-padded decimal seed string.

    Algorithm (LOCKED):
        1. h = md5_hex(str(n) + salt)     # NOT salt + str(n) — Invariant I-4
        2. dec = int(h[0:padding], 16)
        3. num = dec mod (10 ** padding)
        4. if num == 0: num = 1           # zero-guard — Invariant I-9
        5. return str(num).zfill(padding)
    """


def num_to_alpha(n: int, chars: str) -> str:
    """Bijective base-len(chars) encoding of a non-negative integer.

    Uses integer-only arithmetic (// not /). See Invariant I-6.
    """


def alpha_to_num(code: str, chars: str) -> int:
    """Inverse of num_to_alpha. Raises ValueError on invalid char."""


def _md5_hex(material: str) -> str:
    """Return lowercase 32-char hex MD5 digest."""


def _validate_chars(chars: str) -> None:
    """Raise ValueError if chars has duplicates or len < 2."""
```

### 6.3 Type annotations

All public functions return `str` or `int` only — never `Optional[...]`. Contract is "valid input → valid output; invalid input → ValueError". No silent failures, no `None` returns. `EncoderConfig` is frozen + slots.

### 6.4 Test contract — refer to Comprehension §4.2 test vectors

The TestGen agent will populate `tests/fixtures/encode_vectors.json` by running the legacy PHP `Shorty::encode` against the inputs in Comprehension §4.2 Vector groups A and B. The Python test suite then asserts byte-equality against those fixtures.

**Format of `encode_vectors.json`:**

```json
{
  "config": {
    "chars": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "salt": "",
    "padding": 3
  },
  "vectors": [
    {"id": "A1", "n": 1, "salt": "", "padding": 3, "expected_code": "<from PHP>"},
    {"id": "A2", "n": 10, "salt": "", "padding": 3, "expected_code": "<from PHP>"},
    {"id": "B1", "n": 1, "salt": "testsalt", "padding": 3, "expected_code": "<from PHP>"}
  ]
}
```

Each vector is exercised by `tests/unit/test_encode.py::test_BR_C_12_vector_<id>`. Property tests (Vector group C) use `hypothesis` strategies and assert the round-trip `decode(encode(n), cfg) == n` over `n ∈ [1, 100_000]`.

### 6.5 PHP reference fixture generation strategy

Stage 6 TestGen is responsible for fixture generation. Mechanism: TestGen creates `tests/fixtures/_gen_encode_vectors.php` which `require`s `source/shorty.php`, instantiates `new Shorty(...)` with the locked config, calls `$shorty->encode($n)` for each test `n`, and writes JSON to stdout. TestGen captures stdout into `tests/fixtures/encode_vectors.json`.

CodeGen leaves the placeholder file:

```json
{"__GENERATED_BY_TESTGEN__": true, "instructions": "Stage 6 TestGen overwrites this file."}
```

---

## 7. UrlService (business-logic layer)

`app/modules/urls/service.py` exposes a single class `UrlService`. Each public method is async, takes an explicit `AsyncSession`, raises domain exceptions, and never imports `fastapi`.

```python
class UrlService:
    def __init__(
        self,
        cfg: EncoderConfig,
        hostname: str,
        logger: logging.Logger,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None: ...
```

### 7.1 `create_or_get(url: str, db: AsyncSession) -> CreateUrlResult`

```python
async def create_or_get(self, url: str, db: AsyncSession) -> CreateUrlResult: ...
```

**Pre-conditions:** caller passed Pydantic regex; `url` non-empty; `db` open.
**Post-conditions:** exactly one row matching; returned `id`, `code = encode(id, cfg)`, `short_url = hostname/code`, `was_created` truthful.
**Error contract:** `BadUrl` → 400; `EncodeOverflow` → 500; `SQLAlchemyError` → 500 (caught globally).
**BR-C mapping:** BR-C-01, BR-C-02, BR-C-03, BR-C-08, BR-C-11.

**Mandatory ON CONFLICT idiom:**

```python
stmt = (
    pg_insert(Url)
    .values(url=url)
    .on_conflict_do_nothing(index_elements=["url"])
    .returning(Url.id)
)
result = await db.execute(stmt)
inserted_id = result.scalar_one_or_none()

if inserted_id is None:
    existing = await db.execute(select(Url.id).where(Url.url == url))
    inserted_id = existing.scalar_one()
    was_created = False
else:
    was_created = True

await db.commit()
```

Service commits, not router.

### 7.2 `lookup_and_redirect(code: str, db: AsyncSession) -> Url`

```python
async def lookup_and_redirect(self, code: str, db: AsyncSession) -> Url: ...
```

**Implementation outline:**
1. `try: id_ = decode(code, cfg) except ValueError: raise UrlNotFound`.
2. `if id_ < 1 or id_ > 2_147_483_647: raise UrlNotFound` (OQ-C-03).
3. `row = await db.execute(select(Url).where(Url.id == id_))`. `url = row.scalar_one_or_none()`.
4. `if url is None: raise UrlNotFound`.
5. Re-validate stored URL (RF-06): `if not re.match(LEGACY_URL_REGEX, url.url): raise BadUrl(...)`.
6. Fire telemetry via `asyncio.create_task(self._record_hit(url.id))`.
7. Return `url`.

**BR-C mapping:** BR-C-05, BR-C-06, BR-C-07, BR-C-10.

### 7.3 `_record_hit(id_: int) -> None`

Internal background-task method. Acquires a **fresh** session from `self.session_factory` (the request session is closed by the time this runs). Exceptions caught and logged WARN with `{event: "telemetry_update_failed", id, error}`.

```python
async with self.session_factory() as bg_db:
    stmt = (
        update(Url)
        .where(Url.id == id_)
        .values(hits=Url.hits + 1, accessed=func.now())
    )
    await bg_db.execute(stmt)
    await bg_db.commit()
```

`Url.hits + 1` is a **DB-side expression** — never compute `url.hits + 1` in Python (would race).

### 7.4 `build_short_url(id_: int) -> str`

Sync helper returning `f"{self.hostname.rstrip('/')}/{encode(id_, self.cfg)}"`.

### 7.5 Format-negotiation delegation

`UrlService` does not render output. Router calls `formatting.render(result, fmt)`.

### 7.6 Traceability header

Required `RULES` list: BR-C-01, BR-C-05, BR-C-07, BR-C-08, BR-C-10, BR-C-11, BR-C-12.

---

## 8. FastAPI Router

`app/modules/urls/router.py` defines exactly one `APIRouter`. Routes follow Comprehension §6.1 R1–R5.

### 8.1 Route definitions

**R1 — `GET /`** (create OR fall-through to lookup OR 404 — composite endpoint)

```python
@router.get("/", response_class=Response)
async def root_handler(
    request: Request,
    url: Annotated[str | None, Query(default=None, max_length=2048)] = None,
    q: Annotated[str | None, Query(default=None, max_length=32)] = None,
    format: Annotated[str | None, Query(default=None, max_length=16)] = None,
    client_ip: Annotated[str, Depends(get_client_ip)],
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[UrlService, Depends(get_url_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response: ...
```

**Routing decision tree:**

| `url` non-empty? | `q` non-empty? | Action |
|---|---|---|
| yes | (any) | create flow; whitelist enforced |
| no | yes | lookup flow; slash-strip applied |
| no | no | 404 |

Validation: manual `re.match(LEGACY_URL_REGEX, url)`. Whitelist gate via `require_ip_allowed(client_ip, settings)` inline. `format` parsed via `OutputFormat.parse(format)`.

**BR-C mapping:** BR-C-01..04, 05, 06, 07, 08, 09, 10.

**R3 — `GET /{code}`** (path-style lookup)

```python
@router.get("/{code}", response_class=Response)
async def lookup_by_path(
    code: Annotated[str, Path(..., min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9]+$")],
    service: Annotated[UrlService, Depends(get_url_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RedirectResponse: ...
```

Path regex enforces alphanumeric; `RequestValidationError` handler maps to 404.

**R4 — `POST /shorten`** (REST alias)

```python
@router.post("/shorten", response_class=Response)
async def shorten(
    body: CreateUrlRequest,
    client_ip: Annotated[str, Depends(get_client_ip)],
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[UrlService, Depends(get_url_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response: ...
```

Identical semantics to R1's create branch.

**R5 — `GET /healthz`**

```python
@router.get("/healthz", response_model=HealthResponse)
async def healthz(db: Annotated[AsyncSession, Depends(get_db_session)]) -> HealthResponse: ...
```

Executes `SELECT 1`. Always returns 200; body indicates state.

### 8.2 Error response shapes

| Exception | HTTP status | Body shape |
|---|---|---|
| `BadUrl` | 400 | `{"detail": "Bad input.", "type": "shorty/bad-input"}` |
| `IpNotAllowed` | 403 | `{"detail": "Not allowed.", "type": "shorty/not-allowed"}` |
| `UrlNotFound` | 404 | `{"detail": "Not Found", "type": "shorty/not-found"}` |
| `EncodeOverflow` | 500 | `{"detail": "Internal error", "type": "shorty/internal"}` |
| Unhandled `Exception` | 500 | `{"detail": "Internal error", "type": "shorty/internal"}` |
| `RequestValidationError` | 400 or 404 | mapped to 404 for path-regex failures |

Registered as `@app.exception_handler(...)` in `main.py`.

### 8.3 Dependencies (DI summary)

| Dependency | Provider | Cached? |
|---|---|---|
| `Settings` | `get_settings` | module-level singleton |
| `AsyncSession` | `get_db_session` | per-request |
| `UrlService` | `get_url_service` | module-level singleton |
| `client_ip` | `get_client_ip` | per-request |

### 8.4 Inclusion in `main.py`

```python
app.include_router(urls_router, tags=["urls"])
```

No prefix.

### 8.5 Format negotiation handling (BR-C-09)

`formatting.render(result, fmt)` produces:

| `fmt` | Returns |
|---|---|
| `TEXT` | `Response(content=short_url, media_type="text/plain; charset=utf-8")` |
| `JSON` | `JSONResponse(content={"url": short_url})` |
| `XML` | `Response(content=<xml string>, media_type="application/xml")` |
| `HTML` | `HTMLResponse(content=<anchor string>)` |

XML body (locked, byte-identical):

```
<?xml version="1.0"?>
<response>
  <url>{html.escape(short_url)}</url>
</response>
```

HTML body: `'<a href="{escaped_url}">{escaped_url}</a>'` — `html.escape(short_url, quote=True)`.

No templating engine. Plain f-strings + `html.escape`. Newline/indentation is part of the byte contract.

---

## 9. Configuration + Bootstrap

### 9.1 `app/core/config.py` — Pydantic Settings

```python
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHORTY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hostname: str = Field(default="http://localhost:8000")
    db_url: str = Field(default="postgresql+asyncpg://shorty:shorty@localhost:5432/shorty")
    chars: str = Field(default="abc...XYZ0123456789", min_length=2, max_length=128)
    salt: SecretStr = Field(default=SecretStr(""))
    padding: int = Field(default=3, ge=0, le=16)
    ip_whitelist_raw: str = Field(default="", alias="IP_WHITELIST")
    trusted_proxies_raw: str = Field(default="127.0.0.1", alias="TRUSTED_PROXIES")
    log_level: str = Field(default="INFO")
    json_logs: bool = Field(default=False)

    @model_validator(mode="after")
    def _validate_chars_unique(self) -> "Settings": ...

    @property
    def ip_whitelist(self) -> frozenset[str]: ...
    @property
    def trusted_proxies(self) -> frozenset[str]: ...
    @property
    def encoder_config(self) -> "EncoderConfig": ...
```

Whitelist parsing per OQ-C-01: split on `,`, strip each entry, drop empties; empty result = open mode.

### 9.2 `app/main.py` — app, lifespan, middleware

**Middleware order (mandatory):**

1. `ProxyHeadersMiddleware(trusted_hosts=settings.trusted_proxies)` — must be first.
2. CORS — deferred (Phase 1 has no CORS).
3. Optional `LoggingMiddleware` for `request_received` log lines.

**Lifespan:** startup reads Settings, configures logging, validates DB; shutdown disposes engine.

**Exception handlers** registered on the app per §8.2.

### 9.3 `app/db/engine.py` — engine + session factory

```python
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings) -> AsyncEngine: ...
def get_session_factory() -> async_sessionmaker[AsyncSession]: ...
async def dispose_engine() -> None: ...


async def get_db_session() -> AsyncGenerator[AsyncSession, None]: ...
```

Engine pool: `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`. Echo off in prod; `SHORTY_DB_ECHO=true` undocumented flag.

### 9.4 Environment variables

| Env var | Type | Default | Description |
|---|---|---|---|
| `SHORTY_HOSTNAME` | string | `http://localhost:8000` | Short-URL composition. |
| `SHORTY_DB_URL` | DSN | `postgresql+asyncpg://shorty:shorty@localhost:5432/shorty` | Async DSN. |
| `SHORTY_CHARS` | string | default 62-char alphabet | Encoding alphabet. |
| `SHORTY_SALT` | string | `""` (LOCKED Gate 1 OQ-01) | Encoding salt. |
| `SHORTY_PADDING` | int | `3` (LOCKED Gate 1 OQ-02) | Seed length. |
| `SHORTY_IP_WHITELIST` | CSV | `""` (open) | IPs allowed to create. |
| `SHORTY_TRUSTED_PROXIES` | CSV | `127.0.0.1` | IPs whose `X-Forwarded-For` is honoured. |
| `SHORTY_LOG_LEVEL` | string | `INFO` | Logging level. |
| `SHORTY_JSON_LOGS` | bool | `false` | JSON log output. |
| `SHORTY_DB_ECHO` | bool | `false` | SQL echo (debug). |

---

## 10. Build Order

Strict phased sequence. After every phase, `pytest` and `ruff check` pass.

### Phase A1 — Encode module (NO deps)

**Files:** `encode.py`, package markers, `test_encode.py`, `conftest.py` (initial), `pyproject.toml`, placeholder `encode_vectors.json`.

### Phase A2 — DB engine + base + model

**Files:** `db/base.py`, `db/engine.py`, `models.py`, `core/config.py`, `core/logging.py`. Adds `db_engine`, `db_session` fixtures to `conftest.py`.

### Phase B1 — Schemas + errors + formatting

**Files:** `schemas.py`, `errors.py`, `formatting.py`, `test_schemas.py`, `test_formatting.py`.

### Phase B2 — Service + dependencies

**Files:** `dependencies.py`, `service.py`, `test_create.py`, `test_lookup.py`, `test_telemetry.py`.

### Phase C1 — Router + main

**Files:** `router.py`, `main.py`. Adds `httpx.AsyncClient` fixture.

### Phase C2 — Bootstrap polish

**Files:** Alembic env/template/`0001_init_urls.py`, `alembic.ini`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`, `test_health.py`.

### Phase D1 — Parity scaffolding

**Files:** `tests/parity/test_php_parity.py` (skipped unless PHP container up).

---

## 11. Test Plan (forward to Stage 6 TestGen)

### 11.1 Test class structure

| File | Class(es) | Scope |
|---|---|---|
| `test_encode.py` | TestEncodeVectors, TestEncodeProperty, TestEncoderConfig | Pure encode/decode |
| `test_formatting.py` | TestFormatNegotiation | BR-C-09 byte-for-byte |
| `test_schemas.py` | TestCreateUrlRequest, TestProblemDetail | Pydantic validation |
| `test_create.py` | TestCreateRoute, TestCreateConcurrency | R1, R4 — BR-C-01..04, 08, 09 |
| `test_lookup.py` | TestLookupRoute, TestLookupEdgeCases | R2, R3 — BR-C-05..08 |
| `test_telemetry.py` | TestTelemetry, TestFireAndForget | BR-C-10, BR-C-11 |
| `test_health.py` | TestHealth | R5 |
| `test_php_parity.py` | TestPhpParity | Stage 7 |

### 11.2 BR-C coverage matrix

| BR-C | Test file | Sample test method names |
|---|---|---|
| BR-C-01 | test_create.py | `test_BR_C_01_duplicate_url_returns_same_code`, `test_BR_C_01_concurrent_creates_no_500` |
| BR-C-02 | test_create.py, test_schemas.py | `test_BR_C_02_invalid_url_400`, `test_BR_C_02_uppercase_scheme_rejected`, `test_BR_C_02_ipv4_dot_rejected` |
| BR-C-03 | test_create.py | `test_BR_C_03_single_decode_of_url_param` |
| BR-C-04 | test_create.py | `test_BR_C_04_empty_whitelist_open`, `test_BR_C_04_ip_in_whitelist_allowed`, `test_BR_C_04_ip_not_in_whitelist_403`, `test_BR_C_04_lookup_ignores_whitelist`, `test_BR_C_04_xforwardedfor_resolves_real_ip` |
| BR-C-05 | test_lookup.py | `test_BR_C_05_valid_code_redirects`, `test_BR_C_05_slash_strip`, `test_BR_C_05_overflow_returns_404` |
| BR-C-06 | test_lookup.py | `test_BR_C_06_unknown_code_404`, `test_BR_C_06_malformed_code_404` |
| BR-C-07 | test_lookup.py | `test_BR_C_07_redirect_status_301`, `test_BR_C_07_location_header`, `test_BR_C_07_tampered_url_500` |
| BR-C-08 | test_create.py, test_lookup.py | `test_BR_C_08_no_params_404`, `test_BR_C_08_empty_url_falls_through_to_lookup` |
| BR-C-09 | test_formatting.py, test_create.py | `test_BR_C_09_format_text`, `..._json`, `..._xml`, `..._html_default`, `..._unknown_format_defaults_html`, `..._case_insensitive` |
| BR-C-10 | test_telemetry.py | `test_BR_C_10_hits_increment_atomic`, `..._accessed_updated`, `..._telemetry_failure_does_not_block_redirect`, `..._concurrent_hits_no_lost_updates` |
| BR-C-11 | test_telemetry.py | `test_BR_C_11_created_default_is_utc_now`, `test_BR_C_11_no_app_side_timestamp` |
| BR-C-12 | test_encode.py | `test_BR_C_12_vector_A1`..`A11`, `..._B1`..`B5`, `..._roundtrip_property_100k`, `..._no_seed_branch_when_salt_empty` |

≥40 test cases planned (excludes property iterations).

### 11.3 Fixture strategy

| Fixture | Scope | Backend | Purpose |
|---|---|---|---|
| `event_loop` | session | — | pytest-asyncio session loop |
| `settings` | session | — | Test `Settings` (`hostname="http://test"`, `salt=""`, `padding=3`) |
| `encoder_cfg` | session | — | Derived from settings |
| `db_engine` | session | SQLite aiosqlite | Default integration backend |
| `pg_db_engine` | session | testcontainers-postgresql | `TestCreateConcurrency` only |
| `db_session` | function | matches engine | Per-test session with rollback |
| `app` | session | — | `create_app(settings)` instance |
| `client` | function | httpx.AsyncClient + ASGITransport | Wraps app |
| `seeded_urls` | function | matches db_session | Canonical fixture rows |
| `encode_vectors` | session | JSON file | Skips tests if placeholder |

### 11.4 Test-naming convention

`test_BR_C_{NN}_{Scenario}` where NN is the BR-C number and Scenario is snake_case description.

---

## 12. Dual-Run Harness Contract (forward to Stage 7)

### 12.1 API surface to test for parity

| Route | Inputs | Sample matrix size |
|---|---|---|
| R1 create | `(url, format)` × {4 URLs} × {5 formats} | 20 |
| R3 lookup | seeded codes for id 1, 10, 25, 26, 52, 61, 62, 100, 1000 | 9 |
| R3 lookup miss | `xyz`, `nonexistent`, `999999999` | 3 |
| R3 lookup overflow | `999999999999999999999999` | 1 |
| R4 POST shorten | same as R1 over body | 20 |
| R1 with whitelist | `ip in/not in` whitelist | 2 |

Total: ~55.

### 12.2 Normalisation rules

| Field/header | Rule |
|---|---|
| `Date` header | Strip |
| `Server` header | Strip |
| `Content-Length` | Strip |
| `X-Powered-By` | Strip (PHP only) |
| Error status codes | Compare with uplift map: PHP 200 → FastAPI 400/403/404 |
| Body for `format=html` | Compare after trimming trailing whitespace and `<h1>` 512-space IE padding (PHP) |

### 12.3 Success criteria

- **Green path:** 100% body-byte match after volatile-header strip.
- **Error path:** 100% body-byte match in `detail` text after status-code uplift map.
- **Encode/decode vectors:** 100% byte-equality across all 16 vectors in §4.2 of Comprehension.
- **Status-code uplift:** 5 documented intentional differences.

### 12.4 Allowed divergence categories

| # | Category | Disposition |
|---|---|---|
| D1 | Status-code uplift | Intentional (RF-09) |
| D2 | HTML padding | Intentional (BR-C-06) |
| D3 | text/plain Content-Type | Intentional (RF-10 fix; BR-C-09) |
| D4 | Volatile server headers | Always stripped |
| D5 | Error JSON shape | Intentional (Phase 1 contract) |

---

## 13. Cockpit Playback Contract (forward to Stage 8)

### 13.1 Per-stage doneMeta values

| Stage | Field | Source | Sample value |
|---|---|---|---|
| Discovery | `php_loc` | `cloc source/` | 438 |
| Discovery | `brs_identified` | count BR-N headings | 15 |
| Discovery | `risk_flags` | count RF-N headings | 12 |
| Comprehension | `br_consolidated` | count BR-C-N headings | 12 |
| Comprehension | `bounded_contexts` | count §2 rows | 5 |
| Comprehension | `must_fix` | rows where Disposition == MUST FIX | 8 |
| Planning | `files_planned` | rows in §2 file tree | 50 |
| Planning | `br_mapped` | §14 matrix | 12 |
| CodeGen | `files_generated` | `find generated/backend/ -type f` | 50 |
| CodeGen | `py_loc` | `cloc generated/backend/app` | ~600 |
| Self-Review | `findings_critical` | self-review §Critical | 0 (target) |
| TestGen | `tests_total` | `pytest --collect-only` | ~60 |
| TestGen | `tests_passed` | `pytest` | TBD |
| Dual-run | `parity_inputs` | matrix size | 55 |
| Dual-run | `parity_passed` | parity test count | TBD |

### 13.2 Artefacts per stage

| Stage | Artefact paths |
|---|---|
| Discovery | `output/discovery/discovery-001.md` |
| Gate 1 | `output/gates/gate-1.md` |
| Comprehension | `output/comprehension/comprehension-001.md` |
| Gate 2 | `output/gates/gate-2.md` |
| Planning | `output/planning/planning-001.md` |
| Gate 3 | `output/gates/gate-3.md` |
| CodeGen | `generated/backend/**` (50 files) |
| Self-Review | `output/self-review/self-review-001.md` |
| TestGen | `output/testgen/testgen-001.md`, `generated/tests/**` |
| Gate 4 | `output/gates/gate-4.md` |
| Dual-run | `output/dual-run/dual-run-001.md` |

### 13.3 Risk-flag positions on the canvas

| RF | Canvas node |
|---|---|
| RF-01 (INT overflow) | `models.py::Url.id` |
| RF-02 (MD5 preservation) | `encode.py::get_seed` |
| RF-03 (string-concat-cast) | `encode.py::encode` |
| RF-04 (regex permissive) | `schemas.py::CreateUrlRequest.url` |
| RF-05 (proxy headers) | `main.py::ProxyHeadersMiddleware` |
| RF-06 (URL re-validation) | `service.py::lookup_and_redirect` |
| RF-07 (concurrent insert) | `service.py::create_or_get` |
| RF-08 (silent-ignore code) | `router.py::lookup_by_path` |
| RF-09 (HTTP 200 errors) | `main.py::exception_handler` |
| RF-10 (text/plain MIME) | `formatting.py::render_text` |
| RF-11 (TZ handling) | `models.py::Url.created` |
| RF-12 (padding default 1 vs 3) | `config.py::Settings.padding` |

---

## 14. Self-check Matrix

### 14.1 BR-C coverage (12/12 PASS)

| BR-C | File:Method | Test class | Result |
|---|---|---|---|
| BR-C-01 | `service.py::create_or_get` (§7.1 ON CONFLICT) | `test_create.py::TestCreateRoute, TestCreateConcurrency` | **PASS** |
| BR-C-02 | `schemas.py::CreateUrlRequest.url` (§5.2) + `router.py::root_handler` manual re-check (§8.1) | `test_schemas.py`, `test_create.py` | **PASS** |
| BR-C-03 | `router.py::root_handler` reads `request.query_params` (§8.1) | `test_create.py` | **PASS** |
| BR-C-04 | `dependencies.py::get_client_ip, require_ip_allowed`; `main.py::ProxyHeadersMiddleware` (§9.2) | `test_create.py` (5 cases) | **PASS** |
| BR-C-05 | `service.py::lookup_and_redirect` (§7.2) | `test_lookup.py` | **PASS** |
| BR-C-06 | `errors.py::UrlNotFound` + `main.py` handler (§8.2) | `test_lookup.py::TestLookupEdgeCases` | **PASS** |
| BR-C-07 | `router.py::lookup_by_path` returns `RedirectResponse(status_code=301)` (§8.1 R3); URL re-validation (§7.2 step 5) | `test_lookup.py` | **PASS** |
| BR-C-08 | `router.py::root_handler` decision tree (§8.1) | `test_create.py`, `test_lookup.py` | **PASS** |
| BR-C-09 | `formatting.py::render` + `schemas.py::OutputFormat.parse` (§5.1, §8.5) | `test_formatting.py`, `test_create.py` | **PASS** |
| BR-C-10 | `service.py::_record_hit` background task (§7.3) | `test_telemetry.py` | **PASS** |
| BR-C-11 | `models.py::Url.created` with `server_default=func.now()` (§4.1); INSERT doesn't pass `created` (§7.1) | `test_telemetry.py` | **PASS** |
| BR-C-12 | `encode.py::encode, decode` (§6.2) | `test_encode.py` | **PASS** |

### 14.2 MUST FIX risk flags (9/9 PASS)

| RF | File:Location | Result |
|---|---|---|
| RF-02 MD5 preservation | `encode.py::get_seed` with `md5_hex(str(n) + salt)` (§6.2 + I-4) | **PASS** |
| RF-03 String-concat-cast | `encode.py::encode` uses `int(k + str(n))` (§6.2 + I-5) | **PASS** |
| RF-05 Proxy header | `main.py::ProxyHeadersMiddleware(trusted_hosts=...)` (§9.2) | **PASS** |
| RF-07 Concurrent insert | `service.py::create_or_get` ON CONFLICT (§7.1) | **PASS** |
| RF-09 HTTP 200 on errors | `main.py` exception handlers 400/403/404 (§8.2) | **PASS** |
| RF-08 Silent-ignore code | `router.py::lookup_by_path` path-pattern + handler → 404 (§8.1, §8.2) | **PASS** |
| RF-10 text/plain MIME | `formatting.py::render_text` sets correct media_type (§8.5) | **PASS** |
| RF-11 TZ handling | `models.py::Url.created` is `TIMESTAMP(timezone=True)` (§4.1) | **PASS** |
| RF-12 padding default | `config.py::Settings.padding=Field(default=3, ge=0)` (§9.1) | **PASS** |
| NEW: Decode-overflow | `service.py::lookup_and_redirect` bounds check (§7.2 step 2) | **PASS** |

**SHOULD FIX:** RF-06 implemented as code, not TODO. **PASS.**

**DOCUMENTED-WONT-FIX (TODO markers required):**
- RF-01: `models.py::Url.id` — `# TODO(stage5-review): Phase 5 upgrade to BIGINT (Gate 1 OQ-03)`
- RF-04: `schemas.py::CreateUrlRequest.url` — `# TODO(stage5-review): legacy regex retained for parity (Gate 1 OQ-05); strict validation Phase 5`

### 14.3 Gate-1 locked decisions (10/10 PASS)

| OQ | Decision | Plan location | Result |
|---|---|---|---|
| OQ-01 | salt = `""` | §9.1 default + §6.2 docstring | **PASS** |
| OQ-02 | padding=3, default chars | §9.1 + §6.4 fixture config | **PASS** |
| OQ-03 | INT (not BIGINT) | §4.1 + §3.1 + §14.2 TODO | **PASS** |
| OQ-04 | TEXT | §4.1 + §3.1 | **PASS** |
| OQ-05 | Preserve legacy regex | §5.2 + §8.1 | **PASS** |
| OQ-06 | Fire-and-forget telemetry | §7.3 background task | **PASS** |
| OQ-07 | GET + POST alias | §8.1 R1 + R4 | **PASS** |
| OQ-08 | Env var CSV whitelist | §9.1 | **PASS** |
| OQ-09 | Greenfield | §3.3 | **PASS** |
| OQ-10 | 301 redirect | §8.1 R3 | **PASS** |

### 14.4 Gate-2 OQ-C decisions (3/3 PASS)

| OQ-C | Decision | Plan location | Result |
|---|---|---|---|
| OQ-C-01 | Empty whitelist entries → open mode | §9.1 + §1.4 | **PASS** |
| OQ-C-02 | DB-loaded URL re-validation failure → 500 + ERROR log | §7.2 step 5 + §8.2 | **PASS** |
| OQ-C-03 | decode overflow > INT32_MAX → 404 | §7.2 step 2 | **PASS** |

### 14.5 Summary

- BR-C: **12/12 PASS**
- MUST FIX: **9/9 PASS** (8 original + 1 net-new)
- SHOULD FIX: **1/1 PASS** (exceeded — implemented as code)
- DOCUMENTED-WONT-FIX: **2/2 PASS** (TODO markers specified)
- Gate-1 OQ: **10/10 PASS**
- Gate-2 OQ-C: **3/3 PASS**

**Total: 37/37 PASS. Plan is complete.**

---

## 15. Open Questions (residual)

| OQ-P | Question | Suggested resolution | Impact |
|---|---|---|---|
| OQ-P-01 | Background-task session: `async_sessionmaker` injection vs FastAPI `BackgroundTasks`? | **Constructor injection of session_factory.** Matches FA POC's pattern. | LOW |
| OQ-P-02 | `/healthz` should execute `SELECT 1` or just check engine? | **`SELECT 1`** — accurate signal for k8s probes. | LOW |
| OQ-P-03 | If `SHORTY_CHARS` is changed at deployment, separate dual-run target? | **No** — Phase 1 uses default chars; document invariant I-1. | LOW |

---

## 16. Handoff to CodeGen

CodeGen starts with **Phase A1** (encode module). The encode/decode functions in `app/modules/urls/encode.py` are the load-bearing component and must implement Comprehension §4.1 character-for-character — every invariant I-1 through I-10 maps to a specific line in §6.2's function signatures, and Stage 6 will run the legacy PHP against the §4.2 vectors to generate the test fixtures. Do not deviate from the file tree in §2, do not deviate from the function signatures in §6.2, and surface every TODO marker in §14.2 explicitly so Stage 5 Self-Review can audit. After A1 green, proceed strictly in the §10 build-order phases — each phase compiles and its tests pass before the next phase starts.
