"""Queue worker stub.

Detection, tracking, cuts, concat, and Drive upload will run here.
The process stays idle so Compose does not restart-loop before a consumer exists.
"""

from __future__ import annotations

import os
import time


def main() -> None:
    redis_url = os.environ.get("REDIS_URL", "")
    config_dir = os.environ.get("CONFIG_DIR", "config")
    print(f"oxstract worker stub idle (redis={redis_url or 'unset'}, config={config_dir})")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
