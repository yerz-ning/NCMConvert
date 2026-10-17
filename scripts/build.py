import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_NAME = "NCMConvert"


def build_work_dir():
    base = os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"
    return os.path.join(base, APP_NAME + "_build")


def build():
    work = build_work_dir()
    command = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--clean",
        "--name", APP_NAME,
        "--paths", ROOT,
        "--distpath", ROOT,
        "--workpath", work,
        "--specpath", work,
        os.path.join(ROOT, "src", "main.py"),
    ]
    sys.stdout.write(" ".join(command) + "\n")
    return subprocess.call(command, cwd=ROOT)


def main():
    code = build()
    target = os.path.join(ROOT, APP_NAME + (".exe" if os.name == "nt" else ""))
    if code == 0 and os.path.exists(target):
        sys.stdout.write("输出: %s (%d 字节)\n" % (target, os.path.getsize(target)))
    return code


if __name__ == "__main__":
    sys.exit(main())
