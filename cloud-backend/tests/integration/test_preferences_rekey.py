"""Integration tests for E11-S3: operator_preferences re-key migration + isolation.

Real PostgreSQL (testcontainers) — A1 hard gate. Covers:
- AC2  — operator_id is UUID + FK to users(user_id); CHECKs survive (catalog asserts)
- AC3  — migration 0011 DELETEs defunct non-UUID rows, retypes, adds FK; re-applies
- AC1  — two real users (via create_user, A3) have independent prefs; A never touches B
- Sec1 — a body-supplied operator_id cannot write another user's row (token-only id)
- FK   — a prefs row for an unknown user_id is rejected (the FK is real)

Migration-shape decisions (party-mode): DELETE precedes the string->uuid ALTER (D3);
the AC3 seed uses a genuinely NON-UUID-castable TEXT value so an ALTER-before-DELETE
bug cannot pass; isolation seeds TWO FRESH operators via the real create_user path
(NOT the conftest operator/admin synthetics — that path skips real bcrypt).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")
_JWT_SECRET = "integration-test-secret-0123456789abcdef0123456789"
_ISSUER = "oebb-cloud-backend"


@pytest.fixture(scope="module", autouse=True)
def _jwt_env() -> Generator[None, None, None]:
    prev = {k: os.environ.get(k) for k in ("JWT_SECRET", "JWT_ISSUER", "JWT_ALGORITHM")}
    os.environ["JWT_SECRET"] = _JWT_SECRET
    os.environ["JWT_ISSUER"] = _ISSUER
    os.environ["JWT_ALGORITHM"] = "HS256"
    try:
        yield
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        from alembic import command
        from alembic.config import Config

        prev = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        try:
            cfg = Config(_ALEMBIC_INI)
            cfg.set_main_option("sqlalchemy.url", url)
            command.upgrade(cfg, "head")
            yield url
        finally:
            if prev is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = prev


@pytest_asyncio.fixture
async def factory(pg_url: str) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(pg_url)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sm() as session:
        await session.execute(
            text("TRUNCATE operator_preferences, users RESTART IDENTITY CASCADE")
        )
        await session.commit()
    try:
        yield sm
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def app_client(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    from cloud_backend.database import get_db
    from cloud_backend.main import app

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _run(coro):  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _seed_user(
    factory: async_sessionmaker[AsyncSession], *, username: str, password: str, role: str
) -> str:
    """Seed via the REAL creation path (A3) — the app's bcrypt, not a raw hash."""
    from cloud_backend.routes.auth import create_user

    async with factory() as session:
        return await create_user(session, username=username, password=password, role=role)


async def _login(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── AC2 — operator_preferences is UUID + FK to users; CHECKs survive (catalog) ──


@pytest.mark.integration
def test_operator_preferences_is_uuid_fk_with_checks(pg_url: str) -> None:
    """Assert against the catalog, NOT an app-layer 422 (AC2 tightening, Amelia):
    column type is uuid, a FK to users(user_id) exists, the PK survives, and BOTH
    named CHECK constraints are still present after the 0011 ALTER."""
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        async with engine.connect() as conn:
            col_type = (
                await conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name='operator_preferences' AND column_name='operator_id'"
                    )
                )
            ).scalar()
            fk = (
                await conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.table_constraints tc "
                        "JOIN information_schema.constraint_column_usage ccu "
                        "  ON tc.constraint_name = ccu.constraint_name "
                        "WHERE tc.table_name='operator_preferences' "
                        "  AND tc.constraint_type='FOREIGN KEY' "
                        "  AND ccu.table_name='users' AND ccu.column_name='user_id'"
                    )
                )
            ).scalar()
            pk = (
                await conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.table_constraints "
                        "WHERE table_name='operator_preferences' AND constraint_type='PRIMARY KEY'"
                    )
                )
            ).scalar()
            checks = {
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint con "
                        "JOIN pg_class rel ON rel.oid = con.conrelid "
                        "WHERE rel.relname='operator_preferences' AND con.contype='c'"
                    )
                )
            }
        await engine.dispose()

        assert col_type == "uuid", f"operator_id is {col_type}, expected uuid"
        assert fk == 1, "missing FK operator_preferences.operator_id -> users.user_id"
        assert pk == 1, "primary key did not survive the ALTER"
        assert "ck_threshold_sec_valid" in checks, "threshold CHECK lost in migration"
        assert "ck_staleness_threshold_sec_valid" in checks, "staleness CHECK lost in migration"

    _run(_check())


# ── AC3 — migration 0011 drops genuinely non-UUID-castable defunct rows ──────


@pytest.mark.integration
def test_rekey_migration_drops_defunct_rows(
    pg_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Downgrade to 0010, insert a defunct row keyed by a NON-UUID-castable TEXT
    value (the old shared API-key string — NOT a random uuid-string, or an
    ALTER-before-DELETE bug would pass undetected — Amelia/D3), then upgrade head.
    Assert: the defunct row is gone (DELETE ran), the column is uuid, the FK exists."""
    import psycopg2
    from alembic import command
    from alembic.config import Config

    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", pg_url)

    sync_url = pg_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")

    _prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = pg_url
    try:
        command.downgrade(cfg, "0010")
        # At 0010 the column is TEXT again. Clear any rows a prior test left in the
        # module-shared DB, then seed EXACTLY ONE non-UUID-castable defunct row, so
        # the "deleted 1" assertion is deterministic regardless of test ordering.
        conn = psycopg2.connect(sync_url)
        try:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("DELETE FROM operator_preferences")
            cur.execute(
                "INSERT INTO operator_preferences "
                "(operator_id, threshold_sec, staleness_threshold_sec) "
                "VALUES ('shared-api-key-abc', 60, 120)"
            )
        finally:
            conn.close()
        # upgrade head must DELETE-before-ALTER so the ::uuid cast never sees the
        # non-castable string. A wrong ordering raises invalid_text_representation.
        # D1 legibility rider: assert the migration logs the deleted count. We can't
        # use caplog here — alembic's env.py calls fileConfig() at the top of EVERY
        # migration run with disable_existing_loggers=True, which tears down any
        # handler/propagation we attach. So we record warning() calls directly on
        # Logger.warning (immune to fileConfig) for the duration of the upgrade.
        import logging

        warned: list[str] = []
        _orig_warning = logging.Logger.warning

        def _spy_warning(self, msg, *args, **kwargs):  # type: ignore[no-untyped-def]
            try:
                warned.append(str(msg) % args if args else str(msg))
            except Exception:
                warned.append(str(msg))
            return _orig_warning(self, msg, *args, **kwargs)

        monkeypatch.setattr(logging.Logger, "warning", _spy_warning)
        try:
            command.upgrade(cfg, "head")
        finally:
            monkeypatch.undo()
    finally:
        if _prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev

    # D1 legibility: the deleted-count warning was emitted (we seeded 1 defunct row).
    rekey_logs = [m for m in warned if "defunct operator_preferences row" in m]
    assert rekey_logs, "migration did not log the deleted defunct-row count (D1 legibility)"
    assert "deleted 1 defunct" in rekey_logs[-1], rekey_logs[-1]

    conn = psycopg2.connect(sync_url)
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM operator_preferences")
        assert cur.fetchone()[0] == 0, "defunct row was not deleted by the migration"
        cur.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='operator_preferences' AND column_name='operator_id'"
        )
        assert cur.fetchone()[0] == "uuid", "operator_id not retyped to uuid"
    finally:
        conn.close()


@pytest.mark.integration
def test_migration_0011_genuinely_reapplies(pg_url: str) -> None:
    """Downgrade to 0010 then upgrade head — genuinely re-executes the re-key.
    A broken re-apply (e.g. FK already exists / column wrong type) raises."""
    import psycopg2
    from alembic import command
    from alembic.config import Config

    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", pg_url)
    sync_url = pg_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")

    _prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = pg_url
    try:
        command.downgrade(cfg, "0010")
        command.upgrade(cfg, "head")
    finally:
        if _prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev

    conn = psycopg2.connect(sync_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='operator_preferences' AND column_name='operator_id'"
        )
        assert cur.fetchone()[0] == "uuid", "operator_id not uuid after re-apply"
        cur.execute(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name='operator_preferences' AND constraint_type='FOREIGN KEY'"
        )
        assert cur.fetchone() is not None, "FK missing after re-apply"
    finally:
        conn.close()


# ── AC1 — two real users have independent preferences (isolation) ────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_preferences_isolation_two_users(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """A3: two FRESH operators via the real create_user path (NOT the conftest
    synthetics). A PATCH 90 / B PATCH 30 → A GET 90, B GET 30; exactly two rows,
    each FK-valid to its user."""
    await _seed_user(factory, username="op_a", password="op-a-pw-1234", role="operator")
    await _seed_user(factory, username="op_b", password="op-b-pw-1234", role="operator")
    a_t = await _login(app_client, "op_a", "op-a-pw-1234")
    b_t = await _login(app_client, "op_b", "op-b-pw-1234")

    ra = await app_client.patch(
        "/api/v1/operators/me/preferences", json={"threshold_sec": 90}, headers=_bearer(a_t)
    )
    assert ra.status_code == 200, ra.text
    rb = await app_client.patch(
        "/api/v1/operators/me/preferences", json={"threshold_sec": 30}, headers=_bearer(b_t)
    )
    assert rb.status_code == 200, rb.text

    ga = await app_client.get("/api/v1/operators/me/preferences", headers=_bearer(a_t))
    gb = await app_client.get("/api/v1/operators/me/preferences", headers=_bearer(b_t))
    assert ga.json()["threshold_sec"] == 90
    assert gb.json()["threshold_sec"] == 30  # A's write did NOT touch B

    async with factory() as session:
        n = (
            await session.execute(text("SELECT count(*) FROM operator_preferences"))
        ).scalar()
        orphans = (
            await session.execute(
                text(
                    "SELECT count(*) FROM operator_preferences p "
                    "LEFT JOIN users u ON u.user_id = p.operator_id WHERE u.user_id IS NULL"
                )
            )
        ).scalar()
    assert n == 2, f"expected exactly two prefs rows, got {n}"
    assert orphans == 0, "a prefs row is not FK-valid to a real user"


# ── Sec Test 1 — a body-supplied operator_id cannot write another user's row ──


@pytest.mark.integration
@pytest.mark.asyncio
async def test_body_operator_id_cannot_write_other_users_row(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """Identity is token-only: A sends a body that tries to carry B's user_id;
    only A's own row is written, B's row is untouched."""
    uid_b = await _seed_user(
        factory, username="vic_b", password="vic-b-pw-1234", role="operator"
    )
    await _seed_user(factory, username="att_a", password="att-a-pw-1234", role="operator")
    b_t = await _login(app_client, "vic_b", "vic-b-pw-1234")
    a_t = await _login(app_client, "att_a", "att-a-pw-1234")

    # B sets a baseline.
    await app_client.patch(
        "/api/v1/operators/me/preferences", json={"threshold_sec": 60}, headers=_bearer(b_t)
    )
    # A attempts to spoof B via a body operator_id.
    r = await app_client.patch(
        "/api/v1/operators/me/preferences",
        json={"threshold_sec": 120, "operator_id": uid_b},
        headers=_bearer(a_t),
    )
    assert r.status_code == 200
    assert r.json()["operator_id"] != uid_b  # wrote A's row, not B's

    gb = await app_client.get("/api/v1/operators/me/preferences", headers=_bearer(b_t))
    assert gb.json()["threshold_sec"] == 60, "B's row was modified by A's spoofed body"


# ── FK negative — a prefs row for an unknown user_id is rejected ─────────────


@pytest.mark.integration
def test_preference_fk_rejects_unknown_user(pg_url: str) -> None:
    """A raw INSERT of a prefs row whose operator_id has no matching users row
    violates the FK (23503). The endpoint can never produce this — liveness 401s
    an unknown sub first — so a raw INSERT is the only honest way to hit the FK."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        with pytest.raises(IntegrityError) as exc:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO operator_preferences "
                        "(operator_id, threshold_sec, staleness_threshold_sec) "
                        "VALUES (:oid, 60, 120)"
                    ),
                    {"oid": str(uuid.uuid4())},  # no such user
                )
        cause = exc.value.orig
        code = getattr(cause, "pgcode", None) or getattr(cause, "sqlstate", None)
        assert code == "23503", f"expected FK violation 23503, got {code}"
        await engine.dispose()

    _run(_check())


# ── Security Test 2 — uuid SQL-safety: a junk / SQL-metachar `sub` cannot escape ──


def _mint(sub: str, *, role: str = "operator", minutes: int = 5) -> str:
    """Mint a token directly (not via create_access_token) so the `sub` can be an
    arbitrary string — used to drive a non-UUID / SQL-metachar sub through the real
    verify+query path. Signed with the app's integration secret/issuer so it passes
    signature/issuer checks and reaches the `:oid` bind."""
    return jwt.encode(
        {
            "sub": sub,
            "username": "probe",
            "role": role,
            "iss": _ISSUER,
            "exp": datetime.now(UTC) + timedelta(minutes=minutes),
        },
        _JWT_SECRET,
        algorithm="HS256",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_junk_or_sql_metachar_sub_cannot_escape_the_bind(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """Security Test 2: the `sub` flows into the parametrized query as the bound
    `:oid`, never string-formatted. A non-UUID `sub` (incl. SQL metacharacters)
    must NOT corrupt the query, drop a table, or 500 — post-migration the column is
    uuid, so a non-castable sub fails the bind cleanly (DataError → handled), never
    an unparametrized SQL path. We seed a canary row to prove no DELETE/DROP escaped.
    """
    # Seed a real user + a baseline prefs row that must survive the attack.
    canary_uid = await _seed_user(
        factory, username="canary", password="canary-pw-1234", role="operator"
    )
    canary_t = await _login(app_client, "canary", "canary-pw-1234")
    await app_client.patch(
        "/api/v1/operators/me/preferences",
        json={"threshold_sec": 90},
        headers=_bearer(canary_t),
    )

    # Each of these is a `sub` that, if string-interpolated, would break the query
    # or drop the table. With `:oid` binding + a uuid column they cannot.
    for evil_sub in (
        "'; DROP TABLE operator_preferences; --",
        "x' OR '1'='1",
        "not-a-uuid",
        "00000000-0000-0000-0000-000000000000' OR true --",
    ):
        token = _mint(evil_sub)
        rg = await app_client.get(
            "/api/v1/operators/me/preferences", headers=_bearer(token)
        )
        rp = await app_client.patch(
            "/api/v1/operators/me/preferences",
            json={"threshold_sec": 60},
            headers=_bearer(token),
        )
        # The non-UUID sub is rejected at the liveness gate as a non-existent
        # principal → 401 (NOT a 500 leaking the asyncpg DataError, and NEVER a
        # 200 with injected effects). Hardened in assert_user_active after this
        # test surfaced the 500 gap (E11-S3 Security Test 2; gap predates E11-S3).
        assert rg.status_code == 401, f"GET with sub={evil_sub!r} returned {rg.status_code}"
        assert rp.status_code == 401, f"PATCH with sub={evil_sub!r} returned {rp.status_code}"

    # The canary row and the table both survived — no injection escaped.
    async with factory() as session:
        table_ok = (
            await session.execute(text("SELECT to_regclass('public.operator_preferences')"))
        ).scalar()
        canary_threshold = (
            await session.execute(
                text("SELECT threshold_sec FROM operator_preferences WHERE operator_id = :oid"),
                {"oid": canary_uid},
            )
        ).scalar()
    assert table_ok == "operator_preferences", "operator_preferences was dropped!"
    assert canary_threshold == 90, "canary prefs row was tampered with"


# ── AC5 / Security Test 3 — expired + tampered tokens → 401 on GET *and* PATCH ──


@pytest.mark.integration
@pytest.mark.asyncio
async def test_expired_and_tampered_tokens_401_on_both_verbs(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """AC5 / Security Test 3 pinned on the preferences endpoint specifically (the
    shared `Security(get_current_user)` core enforces it, but the named RED-first
    test must cover BOTH verbs — the protected-paths list only had GET + no-token).
    Expired and tampered-signature tokens → 401 on GET and PATCH; never 200, 404, 500.
    """
    uid = await _seed_user(
        factory, username="exp_user", password="exp-pw-1234", role="operator"
    )
    valid = _mint(uid)  # a genuinely valid token for this seeded user
    expired = _mint(uid, minutes=-5)  # exp in the past
    head, payload, sig = valid.split(".")
    tampered = f"{head}.{payload}.{sig[::-1]}"  # reversed sig → guaranteed-invalid

    for bad in (expired, tampered):
        rg = await app_client.get(
            "/api/v1/operators/me/preferences", headers=_bearer(bad)
        )
        rp = await app_client.patch(
            "/api/v1/operators/me/preferences",
            json={"threshold_sec": 60},
            headers=_bearer(bad),
        )
        assert rg.status_code == 401, f"GET with bad token returned {rg.status_code}"
        assert rp.status_code == 401, f"PATCH with bad token returned {rp.status_code}"

    # Sanity: the VALID token still works on both verbs (proves the 401s above are
    # the token's fault, not a broken endpoint).
    assert (
        await app_client.get("/api/v1/operators/me/preferences", headers=_bearer(valid))
    ).status_code in (200, 404)
    assert (
        await app_client.patch(
            "/api/v1/operators/me/preferences",
            json={"threshold_sec": 60},
            headers=_bearer(valid),
        )
    ).status_code == 200
