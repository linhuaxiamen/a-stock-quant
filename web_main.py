"""Web 管理后台入口

用法:
    python web_main.py              # 默认 0.0.0.0:5000
    python web_main.py --port 8080  # 指定端口
    python web_main.py --debug      # 开发模式
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import create_app
import config


def main():
    parser = argparse.ArgumentParser(description="A股量化 Web管理后台")
    parser.add_argument("--host", default=config.WEB.get("host", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=config.WEB.get("port", 5000))
    parser.add_argument("--debug", action="store_true",
                        default=config.WEB.get("debug", False))
    args = parser.parse_args()

    app = create_app()
    print(f"\n  A股量化 Web管理后台")
    print(f"  http://localhost:{args.port}")
    print(f"  按 Ctrl+C 停止\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
