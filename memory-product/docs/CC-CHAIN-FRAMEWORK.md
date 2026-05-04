# CC Chain Framework

## Test-touching stages: mandatory verification

1. Any stage that creates or modifies a file under tests/ MUST run pytest on that file before logging SHIPPED. Run with all env vars the test gates on (CP8_E2E_CONSENSUS=1 etc). On non-zero exit: log STAGE_NN_FAILED with the pytest output captured to /tmp/<chain>/stage-NN-test-output.log.

2. Tests using pytest.mark.skipif(env) MUST be exercised once with the env set in the chain that creates them. Output captured to /tmp/<chain>/stage-NN-test-output.log. Post-flight greps that log for "passed" — absent or "failed" → chain marked DEGRADED.

3. Post-flight runs the non-env-gated test suite as a final smoke: pytest tests/ -x --deselect tests/test_e2e_consensus.py 2>&1 | tail -30. Failure → chain DEGRADED, recommended-next-chain prepends a "fix failing tests" stage.
