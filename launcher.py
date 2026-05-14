import os
from argparse import ArgumentParser
from dotenv import load_dotenv
import uvicorn


def main():
    parser = ArgumentParser()
    parser.add_argument("--host", help="Host to bind the server to", default="127.0.0.1", aliases=["-h"])
    parser.add_argument("--port", help="Port to bind the server to", default=22000, type=int, aliases=["-p"])
    parser.add_argument("--reload", help="Enables auto-reload", action="store_true", aliases=["-r"])
    parser.add_argument("--log-level", help="Log level", default="info",
                        choices=["debug", "info", "warning", "error"])
    parser.add_argument("--env", help="Environment file to load at startup", default=".env", aliases=["-e"])
    parser.add_argument("--overwrite-env", help="If set, this value will overwrite the .env file value",
                        action="store_true", default="false", aliases=['-oe'])
    args = parser.parse_args()

    load_dotenv(args.env)

    HOST = args.host if args.overwrite_env else os.getenv("HOST", args.host)
    PORT = args.port if args.overwrite_env else os.getenv("PORT", args.port)
    LOG_LEVEL = args.log_level if args.overwrite_env else os.getenv("LOG_LEVEL", args.log_level)

    uvicorn.run("saas_flow.app.main:app", host=HOST, port=PORT, reload=args.reload, log_level=LOG_LEVEL)


if __name__ == "__main__":
    main()
