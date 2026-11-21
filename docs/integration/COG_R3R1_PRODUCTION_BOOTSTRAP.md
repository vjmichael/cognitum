# Cognitum R3-R1 — Windows production bootstrap and signed-only enrollment

**Source candidate, not a signed installer and not physical acceptance.**

The new separate native/windows_scm_production Rust crate implements the genuine
CognitumSsmSupervisorV1 SCM bootstrap: LocalSystem/session-zero token check,
kill-on-close kernel Job, zero-worker check, STOP/SHUTDOWN lifecycle. It has no
CI HMAC, no test PID, no Core IPC, no ability to run SSM, and no output channel.
Native compile alone cannot prove physical installed execution.

The script scripts/cog-r5-physical02-r3-r1-enroll-production.ps1 is intended
only for an explicitly approving elevated Windows administrator, after a
separately signed MSI/EXE installer has been staged with independently approved
complete-file SHA256 and publisher certificate pin. It requires an independently
signed cognitum-scm-production.exe, protected code and runtime ancestry, the
closed original Python/NumPy/SciPy manifest and external provenance pin. It
refuses an existing service, CI fixture, missing approval or invalid image.

Only after all preflight checks and user confirmation will it register the
dedicated automatic LocalSystem service, set its restricted service SID, start
the zero-worker bootstrap, and observe the original signed host preflight.
It does not sign files, build an MSI, provision keys, grant Lu authority,
start numerical work, or authorize ACK/output. Partial SCM installation is
left for explicit reviewed recovery, never automatic foreign-service deletion.

**Not yet delivered:** signed MSI/EXE release artifact, externally approved
publisher and release source, independently provisioned production CNG signing,
installed AppContainer original worker, authenticated Lu PURE_COMPUTE grants,
genuine cancellation/restart and physical installed acceptance. The production
bootstrap refuses numerical operation until those distinct contracts exist.

The old native/windows_scm_fixture is and remains CI-only. Never rename or
sign it as the production service.
