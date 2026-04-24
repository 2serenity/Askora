from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE_FILE = ROOT / ".env.example"
LOCAL_DATA_DIR = ROOT / "data"
LOCAL_TRAIN_FILE = LOCAL_DATA_DIR / "train.csv"
PROJECT_NAME = "analytics_workspace"


def print_step(message: str) -> None:
    print(f"[analytics-workspace] {message}")


def resolve_dataset_source() -> Path | None:
    candidates = []

    source_env = os.getenv("SOURCE_TRAIN_CSV", "").strip()
    if source_env:
        candidates.append(Path(source_env))

    candidates.extend(
        [
            Path.home() / "data" / "train.csv",
            ROOT / "train.csv",
            LOCAL_TRAIN_FILE,
        ]
    )

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def ensure_dataset_file() -> None:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    source = resolve_dataset_source()
    if source is None:
        print_step(
            "CSV-датасет не найден. Ожидаю train.csv в папке data/ рядом с проектом "
            "или по пути SOURCE_TRAIN_CSV."
        )
        return

    if source.resolve() == LOCAL_TRAIN_FILE.resolve():
        print_step(f"Использую локальный датасет: {LOCAL_TRAIN_FILE}")
        return

    should_copy = (
        not LOCAL_TRAIN_FILE.exists()
        or LOCAL_TRAIN_FILE.stat().st_size != source.stat().st_size
        or int(LOCAL_TRAIN_FILE.stat().st_mtime) < int(source.stat().st_mtime)
    )
    if should_copy:
        shutil.copy2(source, LOCAL_TRAIN_FILE)
        print_step(f"Скопировал train.csv в рабочую папку data/ из {source}")
    else:
        print_step(f"Локальный train.csv уже актуален: {LOCAL_TRAIN_FILE}")


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        print_step("Файл .env уже найден.")
        return

    if not ENV_EXAMPLE_FILE.exists():
        raise FileNotFoundError("Не найден .env.example, нечего копировать в .env.")

    shutil.copy2(ENV_EXAMPLE_FILE, ENV_FILE)
    print_step("Создал .env из .env.example.")

    content = ENV_FILE.read_text(encoding="utf-8")
    replacements = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip(),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", "").strip(),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "").strip(),
        "LLM_MODEL": os.getenv("LLM_MODEL", "").strip(),
    }
    replaced_any = False
    for key, value in replacements.items():
        if not value:
            continue
        content = content.replace(f"{key}=", f"{key}={value}", 1)
        replaced_any = True
    if replaced_any:
        ENV_FILE.write_text(content, encoding="utf-8")
        print_step("Подставил настройки LLM из переменных окружения.")

    if not replacements["OPENAI_API_KEY"] and not replacements["DEEPSEEK_API_KEY"]:
        print_step("Ключи OPENAI_API_KEY и DEEPSEEK_API_KEY не заданы. Платформа запустится в переносимом локальном режиме (`LLM_PROVIDER=local`).")


def resolve_compose_command() -> list[str]:
    docker_path = shutil.which("docker")
    if docker_path:
        try:
            subprocess.run(
                [docker_path, "compose", "version"],
                check=True,
                capture_output=True,
                text=True,
            )
            return [docker_path, "compose"]
        except subprocess.CalledProcessError:
            pass

    docker_compose_path = shutil.which("docker-compose")
    if docker_compose_path:
        return [docker_compose_path]

    raise RuntimeError(
        "Docker Compose не найден. Установите Docker Desktop и убедитесь, что команды `docker compose` или `docker-compose` доступны."
    )


def ensure_docker_daemon(compose_cmd: list[str]) -> None:
    base_docker_cmd = [compose_cmd[0]]
    try:
        subprocess.run(
            base_docker_cmd + ["info"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        error_output = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            "Docker Desktop установлен, но Docker daemon сейчас недоступен. "
            "Запустите Docker Desktop и дождитесь, пока движок поднимется.\n"
            f"Техническая деталь: {error_output}"
        ) from exc


def run_compose(compose_cmd: list[str], args: list[str]) -> int:
    full_command = compose_cmd + ["--project-name", PROJECT_NAME] + args
    print_step(f"Запускаю: {' '.join(full_command)}")
    process = subprocess.run(full_command, cwd=ROOT)
    return process.returncode


def command_up(compose_cmd: list[str], detach: bool) -> int:
    ensure_env_file()
    ensure_dataset_file()
    args = ["up", "--build"]
    if detach:
        args.append("-d")
    code = run_compose(compose_cmd, args)
    if code == 0:
        print()
        print_step("Стек поднят.")
        print_step("Web: http://localhost:3000")
        print_step("API docs: http://localhost:8000/docs")
        print_step("Demo login: business@demo.local / DemoBusiness123")
    return code


def command_down(compose_cmd: list[str]) -> int:
    return run_compose(compose_cmd, ["down"])


def command_logs(compose_cmd: list[str]) -> int:
    return run_compose(compose_cmd, ["logs", "-f"])


def command_seed(compose_cmd: list[str]) -> int:
    ensure_env_file()
    ensure_dataset_file()
    return run_compose(compose_cmd, ["exec", "api", "python", "-m", "app.seed.seed_demo"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Единый launcher для Analytics Workspace. Без параметров поднимает весь стек."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="up",
        choices=["up", "dev", "down", "logs", "seed"],
        help="up = поднять в фоне, dev = поднять в foreground, down = остановить, logs = смотреть логи, seed = досидить данные",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        compose_cmd = resolve_compose_command()
        ensure_docker_daemon(compose_cmd)
    except RuntimeError as exc:
        print_step(str(exc))
        return 1

    if args.action == "up":
        return command_up(compose_cmd, detach=True)
    if args.action == "dev":
        return command_up(compose_cmd, detach=False)
    if args.action == "down":
        return command_down(compose_cmd)
    if args.action == "logs":
        return command_logs(compose_cmd)
    if args.action == "seed":
        return command_seed(compose_cmd)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
