import os
from argparse import ArgumentParser
from dotenv import load_dotenv
import uvicorn

from app.logger import configure_logging


def main():
    parser = ArgumentParser()
    parser.add_argument("--host", "-H", help="Host to bind the server to", default="127.0.0.1")
    parser.add_argument("--port", "-p", help="Port to bind the server to", default=22000, type=int)
    parser.add_argument("--reload", "-r", help="Enables auto-reload", action="store_true")
    parser.add_argument(
        "--log-retention-days",
        help="How many days of rotated log files to keep",
        default=5,
        type=int,
    )
    parser.add_argument("--log-level", help="Log level", default="info",
                        choices=["debug", "info", "warning", "error"])
    parser.add_argument("--env", "-e", help="Environment file to load at startup", default=".env")
    parser.add_argument("--overwrite-env", "-oe", help="If set, this value will overwrite the .env file value",
                        action="store_true", default=False)
    args = parser.parse_args()

    load_dotenv(args.env)

    host = args.host if args.overwrite_env else os.getenv("HOST", args.host)
    port = args.port if args.overwrite_env else int(os.getenv("PORT", args.port))
    log_level = args.log_level if args.overwrite_env else os.getenv("LOG_LEVEL", args.log_level)

    configure_logging(log_level.upper(), retention_days=args.log_retention_days)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=log_level,
        log_config=None,
    )


if __name__ == "__main__":
    main()
