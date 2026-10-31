import argparse
import os
import sys

from .check import check_series, summary
from .config import SERIES_PATH
from .series import read_series, update


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("нет переменной окружения DATABASE_URL (локально – SmogCast/.env, в GitHub Actions – секрет)")
    return url


# команды с базой: seed – загрузить ряд из CSV, hourly – ежечасный запуск; после обоих ряд в базе проверяется
def run_db(command: str) -> list[str]:
    from . import db, live  # psycopg нужен только командам с базой

    with db.connect(database_url()) as conn:
        if command == "seed":
            print(f"загружено часов: {live.seed(conn)}")
            problems = []
        else:
            result = live.hourly(conn)
            print({k: str(v) for k, v in result.items()})
            problems = [f"запуск: {result['error']}"] if result["status"] == "error" else []
        series = db.read_series(conn)
        print(db.counts(conn))
    print(summary(series))
    return problems + check_series(series)


def main() -> None:
    parser = argparse.ArgumentParser(description="Почасовой ряд PM2.5 и погоды в Алматы из Open-Meteo")
    parser.add_argument(
        "command",
        nargs="?",
        default="update",
        choices=["update", "full", "check", "seed", "hourly", "prev"],
        help="update – дописать свежие часы в CSV, full – выгрузить CSV заново, check – проверить CSV; "
             "seed – загрузить CSV в базу, hourly – ежечасный запуск с базой (ряд, снимки прогнозов, журнал); "
             "prev – архив прошлых прогнозов погоды в CSV",
    )
    parser.add_argument("--max-age-hours", type=int, help="при check: ошибка, если последний час старше")
    args = parser.parse_args()

    if args.command == "prev":
        from . import prev

        print(prev.summary(prev.collect()))
        return
    if args.command in ("seed", "hourly"):
        problems = run_db(args.command)
    elif args.command == "check":
        series = read_series()
        problems = check_series(series, max_age_hours=args.max_age_hours)
        print(summary(series))
    else:
        series, added = update(full=args.command == "full")
        print(f"сохранено в {SERIES_PATH.relative_to(SERIES_PATH.parents[1])}, новых часов: {added}")
        problems = check_series(series)
        print(summary(series))

    if problems:
        print("\nпроблемы:\n" + "\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    print("\nпроверка пройдена")


if __name__ == "__main__":
    main()
