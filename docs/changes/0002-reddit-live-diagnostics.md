---
id: 0002
title: Reddit live 可用性诊断增强
status: accepted
version: V0.5.2
date: 2026-06-24
supersedes: none
related:
  - scripts/check_environment.py
  - scripts/check_environment.sh
  - scripts/run_live.sh
  - docs/environment-check.md
  - docs/troubleshooting.md
  - tests/test_environment_check.py
---

## 背景 / Context

V0.5.1 自检确认：mock、测试、报告生成和失败保护均可用，但 Reddit live 在当前本机环境返回
`HTTP Error 403: Blocked`。这类失败通常不是报告生成逻辑坏了，而是终端网络、代理出口、IP、
User-Agent 或 Reddit 访问策略导致。

原有环境诊断主要检查 DNS 与直连 HTTPS，无法解释“浏览器能打开 Reddit，但终端 live 仍然失败”
这种情况。

## 决策 / Decision

增强 `scripts/check_environment.py`，让它区分三层问题：

- 终端是否配置代理环境变量。
- DNS / HTTPS 是否能直连目标域名。
- Python 通过终端代理设置访问 Reddit 时，是否遇到 403、429、DNS、timeout 或 proxy error。

同时新增 `scripts/check_environment.sh` 作为易复制的诊断入口，并更新 `scripts/run_live.sh` 的失败提示，
引导用户先运行环境诊断，而不是反复 `--force`。

## 架构变化 / Architecture

新增的诊断仍然只使用 Python 标准库，不新增依赖，不保存研究数据，不读取或打印真实 API key。
它会发起一次最小 Reddit `search.json` GET 探测，以贴近 live 预检路径；刚遇到 403 / 429 后不要短时间反复运行。

```text
scripts/check_environment.py
  check_proxy_env()            # 检查并脱敏展示终端代理变量
  check_reddit_policy()        # 代理感知的 Reddit search.json GET 探测
  classify_http_status()       # 403 / 429 / 其他 HTTP 状态分类
  classify_network_error()     # DNS / timeout / reset / proxy 分类
scripts/check_environment.sh   # 使用项目已验证 Python 运行诊断
```

## 测试 / Testing

新增 `tests/test_environment_check.py`，覆盖：

- 代理地址脱敏，不打印用户名密码。
- `NO_PROXY` 只作为排除列表展示，不会被误判为代理服务器。
- SOCKS 代理识别。
- Reddit 诊断探测使用与 live 预检一致的 `search.json` URL、GET 方法和 User-Agent。
- HTTP 403 / 429 分类。
- DNS / timeout / connection reset / proxy error 分类。

真实联网仍不进入单元测试；网络诊断通过手动运行 `scripts/check_environment.py` 验证。

## 影响 / Consequences

- 优点：Reddit live 失败时更容易判断是 DNS、代理、403、429 还是普通网络问题。
- 优点：减少连续 `--force` 造成的 429 风险。
- 代价：环境诊断输出更多；如果代理变量里有特殊格式，仍可能需要人工判断。

## 回滚 / Rollback

可移除 `check_proxy_env()` 与 `check_reddit_policy()` 调用，恢复到只检查 DNS / HTTPS 的旧诊断方式。

## 参考 / References

- `docs/troubleshooting.md`（403、429、DNS、代理排查）
- `docs/environment-check.md`（诊断项说明）
