"""One-command local launcher. Installs CPU dependencies in a machine-local venv."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if not (3, 11) <= sys.version_info < (3, 14):
        raise SystemExit("Python 3.11–3.13이 필요합니다. 검증 버전은 Python 3.12입니다.")
    root = Path(__file__).resolve().parent
    runtime = Path(os.environ.get("LOCALAPPDATA", str(Path.home()/".local/share"))) / "Promotion-AI"
    env_dir = runtime / f"venv-py{sys.version_info.major}.{sys.version_info.minor}"
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print("전용 Python 환경을 준비합니다.", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(env_dir)], check=True)
    requirement = root / "requirements-serving.txt"
    stamp = env_dir / "promotion-requirements.sha256"
    digest = hashlib.sha256(requirement.read_bytes()).hexdigest()
    if not stamp.is_file() or stamp.read_text().strip() != digest:
        print("CPU 실행 패키지를 설치합니다. 배경 제거에는 사전 학습된 U2Net을 사용합니다.", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirement)], check=True)
        stamp.write_text(digest)
    arguments = sys.argv[1:]
    if arguments == ["--setup-only"]:
        print("실행 환경 준비 완료:", python)
        return
    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    try:
        result = subprocess.run([str(python), "-m", "promotion_assistant", *arguments], cwd=root, env=environment)
        raise SystemExit(result.returncode)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
