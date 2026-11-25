from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    settings.require()
    _pool = ConnectionPool(
        settings.DATABASE_URL,
        min_size=1,
        max_size=6,
        timeout=20,
        open=False,
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
    )
    _pool.open()
    _pool.wait(timeout=25)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pool() -> ConnectionPool:
    if _pool is None:
        init_pool()
    return _pool


@contextmanager
def tx(user_id=None):
    """Transaction running as the restricted app role with the caller identity set.

    RLS reads app.user_id, so forgetting this wrapper fails closed: the role has
    no privileges outside what the policies allow.
    """
    if _pool is None:
        init_pool()
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute("set local role future_path_app")
            conn.execute("select set_config('search_path', 'future_path, public', true)")
            conn.execute(
                "select set_config('app.user_id', %s, true)",
                (str(user_id) if user_id else "",),
            )
            yield conn
