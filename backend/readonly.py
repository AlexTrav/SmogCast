"""Пользователь базы только для чтения для API: make -C backend readonly.

Подключается владельцем базы (DATABASE_URL из SmogCast/.env), создаёт роль smogcast_api или меняет ей пароль,
даёт право только на select (и на таблицы, которые появятся позже), запрещает запись на уровне сессии
и пишет строку подключения API в /out/.env.api (SmogCast/.env.api, в git не попадает). Пароль не печатается.
"""
import os
import secrets
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

ROLE = "smogcast_api"
OUT = "/out/.env.api"


def main() -> None:
    url = os.environ["DATABASE_URL"]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(url, connect_timeout=30, autocommit=True) as conn:
        owner, database = conn.execute("select current_user, current_database()").fetchone()
        role = sql.Identifier(ROLE)
        exists = conn.execute("select 1 from pg_roles where rolname = %s", (ROLE,)).fetchone()
        verb = "alter" if exists else "create"
        conn.execute(sql.SQL(verb + " role {} with login password {}").format(role, sql.Literal(password)))
        for statement in (
            "grant connect on database {db} to {role}",
            "grant usage on schema public to {role}",
            "grant select on all tables in schema public to {role}",
            # таблицы, которые владелец создаст потом, тоже будут доступны на чтение
            "alter default privileges for role {owner} in schema public grant select on tables to {role}",
            # даже если права когда-нибудь расширят, сессии API остаются только для чтения
            "alter role {role} set default_transaction_read_only = on",
            "alter role {role} set statement_timeout = '15s'",
        ):
            conn.execute(sql.SQL(statement).format(role=role, owner=sql.Identifier(owner),
                                                   db=sql.Identifier(database)))
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[1]
    api_url = urlunsplit(parts._replace(netloc=f"{ROLE}:{password}@{host}"))
    with open(OUT, "w", encoding="utf-8") as file:
        file.write(f"# строка подключения API: пользователь {ROLE}, только чтение (make -C backend readonly)\n")
        file.write(f"DATABASE_URL={api_url}\n")
    print(f"роль {ROLE}: {'пароль обновлён' if exists else 'создана'}, права только на чтение; "
          f"строка подключения – в SmogCast/.env.api")


if __name__ == "__main__":
    main()
