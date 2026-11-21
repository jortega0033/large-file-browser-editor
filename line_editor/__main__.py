"""CLI: python -m line_editor --data-dir <path> --port <port>"""

import argparse
import sys

from .app import create_server
from .storage import StoreError


def _port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer") from None
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(prog="line_editor")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", required=True, type=_port)
    args = parser.parse_args(argv)  # argparse errors exit with code 2

    try:
        server = create_server(args.data_dir, args.port)
    except StoreError as e:
        print(f"line_editor: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"line_editor: cannot listen on port {args.port}: {e.strerror or e}", file=sys.stderr)
        return 2

    server.log_requests = True
    try:
        print(f"Serving on http://127.0.0.1:{server.port}/", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
