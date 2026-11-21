# Cognitum SCM acceptance fixture (not a production service)

This standalone zero-dependency Rust Windows **SCM service binary** copies the narrow service lifecycle pattern from Lu Core PR #244 but does not share Lu's private pipe or grant issuer. The binary only becomes active when built with `--features acceptance-fixture`.

It registers a fixed `CognitumSsmNativeFixtureV1` Windows SCM service name, verifies the LocalSystem token/session 0, creates a service-owned kill-on-close Job, launches the **same binary** into one fixed diagnostic child via `CREATE_SUSPENDED`, checks native Job membership before `ResumeThread`, reports RUNNING, and reaps/kills the entire Job on SCM STOP. No endpoint, user-driven commands, SSM computation, OS-custody promotion, signing key, installer or output release.

Only an ephemeral GitHub hosted Windows VM may install this **unsigned fixture** for kernel/SCM lifecycle qualification. Physical production acceptance still requires an independently signed installed Cognitum service and installer, independently protected signer/receipt custody, authorized Core Health enrollment, real fixed SSM dispatch under SCM-owned workers, and Linux delegated cgroup restart evidence. None are satisfied by this fixture.
