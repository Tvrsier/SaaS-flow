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
    parser.add_argument("--log-level", help="Log level", default="info",
                        choices=["debug", "info", "warning", "error"])
    parser.add_argument("--env", "-e", help="Environment file to load at startup", default=".env")
    parser.add_argument("--overwrite-env", "-oe", help="If set, this value will overwrite the .env file value",
                        action="store_true", default="false")
    args = parser.parse_args()

    load_dotenv(args.env)

    HOST = args.host if args.overwrite_env else os.getenv("HOST", args.host)
    PORT = args.port if args.overwrite_env else os.getenv("PORT", args.port)
    LOG_LEVEL = args.log_level if args.overwrite_env else os.getenv("LOG_LEVEL", args.log_level)

    configure_logging(LOG_LEVEL.upper())

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=args.reload,
        log_level=LOG_LEVEL,
        log_config=None,
    )


if __name__ == "__main__":
    main()
