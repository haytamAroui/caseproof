"""Run the synthetic reviewer workbench on loopback only. No uploads/live LLM calls."""

import argparse

import uvicorn

from apps.api.synthetic_review_app import create_demo_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Use a non-privileged loopback port")
    uvicorn.run(create_demo_app(), host="127.0.0.1", port=args.port, proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
