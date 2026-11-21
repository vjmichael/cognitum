# Cognitum Windows SCM acceptance fixture — real SSM R1

A **test-only** standalone zero-dependency Rust Windows Service Control Manager (SCM) binary, modeled after the native service-lifecycle pattern of Lu Core's SCM implementation, but with **no shared control pipe** or Core authority.

- `--features acceptance-fixture`: original fixed suspended diagnostic child, SCM-owned Job, service STOP/empty check.
- `--features ssm-fixture`: additionally enables **true Cognitum Python SSM numerical worker**, preapproved fixed code and test source hashes, an original-turn HMAC test intent (one use, nonce), fsynced prelaunch and service-owned unsigned kernel-stop record, actual SSM numerical equality and SCM restart replay refusal.
- Without explicit `acceptance-fixture`, service mode cannot start. No unrestricted/model-origin command or service public endpoint is implemented.
- The test MAC key is randomly created **per CI run and embedded in the unsigned executable**; it is NOT a protected production credential. The worker currently inherits LocalSystem and is **not restricted/AppContainer**. CI's source workspace is not an independently pinned signed installer. Do not use the executable in production and do not treat its HMAC/unsigned stop as independent installed authority.
- Native exact-source CI `cog-r5-physical02-r1-ssm.yml` intentionally records all production signing, independently signed stop, Core grant/Health and output release states **false**. Production work is assigned to PHYSICAL-02-R2.

Qualified source: `4aaaae30b5c02f63f39014c0d100b87c69e5b431`, [native SCM run](https://github.com/vjmichael/cognitum/actions/runs/44938794334) 3/3 pass, [C01–C19 run](https://github.com/vjmichael/cognitum/actions/runs/44938794280) 8/8 pass.
