import argparse
import json
from pathlib import Path

from app.main import create_app

SPEC_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Экспорт и проверка OpenAPI-контракта")
    parser.add_argument("--check", action="store_true", help="Проверить файл без перезаписи")
    args = parser.parse_args()
    schema = create_app().openapi()

    if args.check:
        if not SPEC_PATH.exists() or json.loads(SPEC_PATH.read_text(encoding="utf-8")) != schema:
            parser.exit(1, "OpenAPI устарел. Выполни: python -m scripts.export_openapi\n")
        print("OpenAPI совпадает с приложением")
        return

    SPEC_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Обновлён openapi.json")


if __name__ == "__main__":
    main()
