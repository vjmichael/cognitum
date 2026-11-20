# SSM-02-R1 — Native acceptance closeout

**ACCEPTED, bounded scope.** Exact source `d64194a2a8c11991f714b4afd48e2b6936fc8d9d`; [regression 44794036745](https://github.com/vjmichael/cognitum/actions/runs/44794036745) 4/4 and [integration 44794036814](https://github.com/vjmichael/cognitum/actions/runs/44794036814) 8/8, completed success. All four R1 cells passed. Independently downloaded and rehashed all eight original R1/SSM-02 archives against CI SHA-256, ZIP CRC and unique paths; every internal artifact matched, every receipt source/status/test inventory and authorization flag matched; four R1 predecessor receipt links and inherited source pin values matched. 48 internal file hashes, 32 deterministic exact file occurrences (eight unique, identical across four platforms). Direct JUnit re-audit: 132 R1 +160 SSM-02 no-skip cases =292. Earlier 38 foundational +115 inherited per target required by upstream same-head gates, giving 904 cumulative SSM-chain test occurrences across four cells (not all re-audited in this archive pair). No new local execution of hosted code. No claim of general nonlinear synthesis, optimal controller, physical safety or production admission.

| Target | Archive ID | ZIP SHA-256 | Receipt SHA-256 | Dedicated tests |
|---|---:|---|---|---:|
| Windows 3.13 | 14658776886 | 19e7da2796b9536308ed11f5870c80eec7731a7f49d4a279671c0001a7658d9e | adb97a554f537065fe269852846523720036b0db95b2910d2187d30bd38df8cd | 33 |
| Windows 3.13 | 14658966648 | 7adc71bc4e0ffc2c92ea6f24d5f40a4bf89ef2f04ed3499f74c86d9a690e76cd | 7e5316069df80d573bfe89418fec752bfa560609c7da4d7fbc1aaa56461e3a7f | 40 |
| Linux 3.11 | 14657463055 | cbfcea4567d4c5b1db6aa3097ba0ec9d6618430dba73107cc0bb06009e510ad6 | cf452026131123e49cd2c4cfb58284f0ed6e308586832f305fa0b324b35ebddc | 33 |
| Linux 3.11 | 14657369993 | 56b043a5af93695b867037bbbee6c50bd4bbccb392263264c5db86338c8fb7cc | 6592e8135cf3473e6c3f00518b3d2f0af9aeeb3352e1daa55abd03ef41b7df14 | 40 |
| Linux 3.13 | 14656834576 | 3380909343e08d7cbfd300b8889ccd39611bfc20c8901440e487e69dbdeffbe7 | 5b270fc039aa76da8055f900355d35481a6998b100135521e9525e2f02f68e7a | 33 |
| Linux 3.13 | 14658821141 | e7fab1ad0ca77e4abea3afce1571cfd214c84688f1d3b47aa8583a37a53e704c | e16d97d6b22fd833ffcf0ea05660a69e7d994d60e16ef288930e41f6eb424c9f | 40 |
| Windows 3.11 | 14657343254 | 606c3ecb6d1b9cdbe8493805a3b8a743ab151ae6fd6ecad10b78247232eb2ddc | 00594c645cf81c2b53fed8a1af1ebd50c66eec4adf1a3a9e00c53b3adb36f40c | 33 |
| Windows 3.11 | 14657398346 | 084b2f6e50e49062aa85c173db662fe9ccf679550f5de6ed5f7cbe119e9a166a | b897e439fac8335530c1a8a39daa206835be9a48500f6c11ba6a9eedf54ae68a | 40 |

Previous local report [SSM02_R1](SSM02_R1.md) remains the historical candidate snapshot. DS13–16 now have scoped native accepted evidence, broader capability rows remain partial. DS01–12 previous accepted evidence retained. SSM-03 follows as an independently tested new candidate. No overlapping CI.
