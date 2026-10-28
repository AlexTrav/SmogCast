import argparse
import sys

from .check import check_series, summary
from .config import SERIES_PATH
from .series import read_series, update


def main() -> None:
    parser = argparse.ArgumentParser(description="Почасовой ряд PM2.5 и погоды в Алматы из Open-Meteo")
    parser.add_argument(
        "command",
        nargs="?",
        default="update",
        choices=["update", "full", "check"],
        help="update – дописать свежие часы, full – выгрузить весь ряд заново, check – только проверить",
    )
    parser.add_argument("--max-age-hours", type=int, help="при check: ошибка, если последний час старше")
    args = parser.parse_args()

    if args.command == "check":
        series = read_series()
        problems = check_series(series, max_age_hours=args.max_age_hours)
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
