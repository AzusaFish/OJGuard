#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def write_result(path: str, payload: dict[str, object]) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compile_cpp(source: str, binary: str, result_path: str) -> int:
    started = time.monotonic()
    completed = subprocess.run(
        ["g++", "-std=c++17", "-O2", "-pipe", source, "-o", binary],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    write_result(
        result_path,
        {
            "status": "OK" if completed.returncode == 0 else "COMPILE_ERROR",
            "exit_code": completed.returncode,
            "compiler_stdout": completed.stdout[-20000:],
            "compiler_stderr": completed.stderr[-20000:],
            "binary_relative_path": "program" if completed.returncode == 0 else None,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return 0


def run_program(
    binary: str,
    input_path: str,
    time_limit_ms: int,
    output_limit_bytes: int,
    result_path: str,
) -> int:
    started = time.monotonic()
    timed_out = False
    with open(input_path, "rb") as stdin:
        process = subprocess.Popen(
            [binary],
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(binary).parent),
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        try:
            stdout, stderr = process.communicate(timeout=time_limit_ms / 1000)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate()

    output_truncated = len(stdout) > output_limit_bytes or len(stderr) > output_limit_bytes
    stdout = stdout[:output_limit_bytes]
    stderr = stderr[:output_limit_bytes]
    if timed_out:
        status = "TIME_LIMIT_EXCEEDED"
    elif output_truncated:
        status = "OUTPUT_LIMIT_EXCEEDED"
    elif process.returncode == 0:
        status = "OK"
    else:
        status = "RUNTIME_ERROR"
    write_result(
        result_path,
        {
            "status": status,
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "duration_ms": round((time.monotonic() - started) * 1000),
            "timed_out": timed_out,
            "output_truncated": output_truncated,
        },
    )
    return 0


def run_checker(
    binary: str,
    answer_path: str,
    output_path: str,
    time_limit_ms: int,
    output_limit_bytes: int,
    result_path: str,
) -> int:
    started = time.monotonic()
    timed_out = False
    process = subprocess.Popen(
        [binary, answer_path, output_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(Path(binary).parent),
        env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
    )
    try:
        stdout, stderr = process.communicate(timeout=time_limit_ms / 1000)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    output_truncated = len(stdout) > output_limit_bytes or len(stderr) > output_limit_bytes
    if timed_out:
        status = "TIME_LIMIT_EXCEEDED"
    elif output_truncated:
        status = "OUTPUT_LIMIT_EXCEEDED"
    elif process.returncode in (0, 1):
        status = "OK"
    else:
        status = "RUNTIME_ERROR"
    write_result(
        result_path,
        {
            "status": status,
            "exit_code": process.returncode,
            "stdout": stdout[:output_limit_bytes].decode("utf-8", errors="replace"),
            "stderr": stderr[:output_limit_bytes].decode("utf-8", errors="replace"),
            "duration_ms": round((time.monotonic() - started) * 1000),
            "timed_out": timed_out,
            "output_truncated": output_truncated,
        },
    )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return 64
    action = argv[1]
    try:
        if action == "compile" and len(argv) == 5:
            return compile_cpp(argv[2], argv[3], argv[4])
        if action == "run" and len(argv) == 7:
            return run_program(argv[2], argv[3], int(argv[4]), int(argv[5]), argv[6])
        if action == "checker" and len(argv) == 8:
            return run_checker(
                argv[2], argv[3], argv[4], int(argv[5]), int(argv[6]), argv[7]
            )
    except Exception as exc:
        result_path = argv[-1] if len(argv) > 2 else "/tmp/result.json"
        write_result(
            result_path,
            {
                "status": "INFRASTRUCTURE_ERROR",
                "exit_code": None,
                "stdout": "",
                "stderr": f"{type(exc).__name__}: {exc}",
                "duration_ms": 0,
                "timed_out": False,
                "output_truncated": False,
            },
        )
        return 0
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
