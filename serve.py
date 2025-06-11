#!/usr/bin/env python3
"""Simple HTTP server for previewing the static site."""

import http.server
import socketserver
import sys
import os
from pathlib import Path


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    directory = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('.')
    os.chdir(directory)

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(('', port), handler) as httpd:
        print(f"Serving {directory.resolve()} on http://localhost:{port}")
        httpd.serve_forever()


if __name__ == '__main__':
    main()
