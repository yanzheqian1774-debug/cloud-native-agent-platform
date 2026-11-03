# 2026-09-22 规划结果证据提交门禁

第一次正常提交的 pytest 门禁：1 failed、2148 passed、376 skipped，168.08秒；失败项 test_local_https_outputs_and_metering_are_independent[invalid-inner-SUCCEEDED-INVALID]。未提交，未跳过hook。

一次有记录的单项诊断：通过；RESULT_ACCEPTED/VALIDATE_RESPONSE，decision_seconds0.395181，worker已回收。该结果不能抹去整套失败或确证失败根因。正在补采同一整套门禁的JUnit deadline诊断；没有改变测试断言或超时。此为本地合成HTTPS测试，不是供应商实际调用证据。

整套诊断运行2149 passed、376 skipped，164.71秒；对应deadline记录见planning-gate-readback.json。整套失败未在这次诊断复现，根因尚未确证，不声称已修复。无代码、断言或timeout改动。
