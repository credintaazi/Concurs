"""Container entrypoint for cloud hosting (Render, Railway, Fly.io, a VPS, ...).

Persistent disks are usually mounted owned by root. When started as root, this
prepares DATA_DIR for the unprivileged `quiz` user, drops privileges, and then
replaces itself with exactly one uvicorn worker listening on $PORT.

One worker is a hard requirement: WebSocket rooms and rate limits live in
process memory (see "Runtime limits" in README.md).
"""
import os
import pwd
from pathlib import Path


def prepare_data_dir(uid: int, gid: int) -> None:
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        return
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    for path in [root, *root.rglob("*")]:
        os.lchown(path, uid, gid)


def main() -> None:
    if os.getuid() == 0:
        user = pwd.getpwnam("quiz")
        prepare_data_dir(user.pw_uid, user.pw_gid)
        os.setgroups([])
        os.setgid(user.pw_gid)
        os.setuid(user.pw_uid)
        os.environ["HOME"] = user.pw_dir
    port = os.environ.get("PORT", "8000")
    os.execvp("uvicorn", [
        "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port,
        "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*",
    ])


if __name__ == "__main__":
    main()
