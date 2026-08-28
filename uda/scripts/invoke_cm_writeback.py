import argparse
import json
import os
from pathlib import Path


class CMWritebackError(Exception):
    pass


def load_payload(path: Path) -> dict:
    if not path.exists():
        raise CMWritebackError(f"Payload file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise CMWritebackError("Governance payload must be a JSON object")
    return payload


def write_status(path: Path, status: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(status, file, indent=2)


def require_env(name: str) -> str:
    # Centralized required-env validation keeps error messages consistent across modes.
    value = os.getenv(name, "").strip()
    if not value:
        raise CMWritebackError(f"Missing required environment variable: {name}")
    return value


def invoke_with_snowflake(payload: dict) -> dict:
    try:
        import snowflake.connector
    except Exception as exc:  # pragma: no cover
        raise CMWritebackError(
            "snowflake-connector-python is required for CM writeback mode 'snowflake'"
        ) from exc

    account = require_env("CM_SNOWFLAKE_ACCOUNT")
    user = require_env("CM_SNOWFLAKE_USER")
    password = require_env("CM_SNOWFLAKE_PASSWORD")
    warehouse = require_env("CM_SNOWFLAKE_WAREHOUSE")
    database = require_env("METADATA_DATABASE")
    schema = require_env("METADATA_SCHEMA")
    procedure = require_env("METADATA_STORED_PROCEDURE")
    role = os.getenv("CM_SNOWFLAKE_ROLE", "").strip() or None

    conn = snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )

    # Stored procedure contract accepts one JSON payload argument.
    sql = f"CALL {database}.{schema}.{procedure}(PARSE_JSON(%s))"

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (json.dumps(payload),))
            row = cursor.fetchone()
    finally:
        conn.close()

    result = row[0] if row else None
    return {
        "cm_writeback_status": "SUCCESS",
        "mode": "snowflake",
        "procedure": f"{database}.{schema}.{procedure}",
        "result": result,
    }


def invoke_mock(payload: dict) -> dict:
    # Mock mode allows pipeline validation without external Snowflake connectivity.
    return {
        "cm_writeback_status": "SUCCESS",
        "mode": "mock",
        "message": "Mock mode: CM writeback invocation simulated",
        "request_id": payload.get("request_id"),
        "activity_type": payload.get("activity_type"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke CM stored procedure writeback")
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument(
        "--mode",
        required=False,
        default=os.getenv("CM_WRITEBACK_MODE", "mock"),
        choices=["mock", "snowflake"],
        help="CM invocation mode",
    )
    args = parser.parse_args()

    payload = load_payload(Path(args.payload_file))

    # Dispatch by mode so workflow behavior is explicit and easy to test.
    if args.mode == "snowflake":
        status = invoke_with_snowflake(payload)
    else:
        status = invoke_mock(payload)

    write_status(Path(args.status_file), status)
    print(f"CM writeback completed. mode={status['mode']} status={status['cm_writeback_status']}")


if __name__ == "__main__":
    try:
        main()
    except CMWritebackError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
