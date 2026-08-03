from pathlib import Path

from backend.app.runner import DockerRunner, ExecutionStatus, ResourceLimits


def compile_and_run(runner: DockerRunner, source: str, payload: bytes) -> str:
    compile_result, session = runner.compile_cpp(source_relative_path=source)
    if compile_result.status is not ExecutionStatus.OK:
        raise RuntimeError(f"compile failed for {source}: {compile_result.compiler_stderr}")
    execution = runner.execute(
        session=session,
        input_payload=payload,
        limits=ResourceLimits(time_limit_ms=2_000),
    )
    if execution.status is not ExecutionStatus.OK:
        raise RuntimeError(f"execution failed for {source}: {execution.model_dump()}")
    return execution.stdout.strip()


def main() -> None:
    root = Path.cwd()
    runner = DockerRunner(
        packages_root=root / "demo",
        sessions_root=root / "data" / "runner-sessions",
    )
    overflow_input = f"3000\n{' '.join(['1000000'] * 3000)}\n".encode()
    counterexample = b"3\n5 -100 6\n"

    oracle_overflow = compile_and_run(
        runner, "maximum_segment_score/solutions/oracle.cpp", overflow_input
    )
    reference_overflow = compile_and_run(
        runner, "maximum_segment_score/solutions/reference.cpp", overflow_input
    )
    oracle_counterexample = compile_and_run(
        runner, "maximum_segment_score/solutions/oracle.cpp", counterexample
    )
    wrong_counterexample = compile_and_run(
        runner, "maximum_segment_score/solutions/wrong_positive_sum.cpp", counterexample
    )
    checker_compile, checker_session = runner.compile_cpp(
        source_relative_path="maximum_segment_score/checker/checker.cpp"
    )
    if checker_compile.status is not ExecutionStatus.OK:
        raise RuntimeError(f"Checker compile failed: {checker_compile.compiler_stderr}")
    checker_probe = runner.probe_checker(
        session=checker_session,
        answer_payload=b"15\n",
        contestant_output=b"15\nTHIS_OUTPUT_MUST_BE_REJECTED\n",
    )
    validator_compile, validator_session = runner.compile_cpp(
        source_relative_path="maximum_segment_score/validators/validator.cpp"
    )
    if validator_compile.status is not ExecutionStatus.OK:
        raise RuntimeError(f"Validator compile failed: {validator_compile.compiler_stderr}")
    validator_probe = runner.execute(
        session=validator_session,
        input_payload=b"1\n1000000000\n",
    )

    print(f"overflow_oracle={oracle_overflow}")
    print(f"overflow_reference={reference_overflow}")
    print(f"counterexample_oracle={oracle_counterexample}")
    print(f"counterexample_wrong={wrong_counterexample}")
    print(f"checker_trailing_output_exit={checker_probe.exit_code}")
    print(f"statement_legal_value_validator_exit={validator_probe.exit_code}")
    if oracle_overflow == reference_overflow:
        raise RuntimeError("overflow defect was not reproduced")
    if oracle_counterexample == wrong_counterexample:
        raise RuntimeError("wrong-solution defect was not reproduced")
    if checker_probe.status is not ExecutionStatus.OK or checker_probe.exit_code != 0:
        raise RuntimeError("Checker trailing-output bypass was not reproduced")
    if validator_probe.exit_code != 1:
        raise RuntimeError("statement/Validator mismatch was not reproduced")
    print("runner_smoke=PASS")


if __name__ == "__main__":
    main()
