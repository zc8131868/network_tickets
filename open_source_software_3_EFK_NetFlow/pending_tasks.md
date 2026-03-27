# Syslog Integration — Pending Tasks

> Code is already in place. Follow these steps to activate and verify.
> Reference: [openclaw_syslog_integration.md](openclaw_syslog_integration.md)

---

## Step 1 — Restart Django

Restart so the new code, settings, and URL route take effect.

```bash
sudo systemctl restart network_tickets
```

Verify Django is running:

```bash
sudo systemctl status network_tickets
```

---

## Step 2 — Test the API from the host

Run from the server (`196.21.5.228`) to confirm Django can talk to Elasticsearch:

```bash
curl -sS -X POST "https://cmhk-it-netcare.com/api/openclaw/syslogs/search/" \
  -H "Authorization: Bearer netcare-openclaw-syslog-2026" \
  -H "Content-Type: application/json" \
  -d '{"start":"now-1h","end":"now","size":5}'
```

**Expected:** JSON with `"success": true` and a `results` array (may be empty if no logs in the last hour — that's OK).

**If 401:** Bearer token mismatch — check `env.conf` → `OPENCLAW_INTERNAL_TOKEN`.

**If 502:** Django cannot reach Elasticsearch — check:
- Is Elasticsearch running? `docker ps | grep elastic`
- Is `ELASTIC_URL` correct in `env.conf`?
- Does the CA cert path exist? `ls -la /it_network/open_source_software_3_EFK_NetFlow/certs/ca.cer`

**If 500 / import error:** The `elasticsearch` Python package may not be installed in your Django virtualenv. Run:

```bash
pip install elasticsearch
```

---

## Step 3 — Test from inside the OpenClaw gateway container

This confirms the OpenClaw container can reach Django over the network:

```bash
docker exec openclaw-openclaw-gateway-1 \
  curl -sS -X POST "https://cmhk-it-netcare.com/api/openclaw/syslogs/search/" \
  -H "Authorization: Bearer netcare-openclaw-syslog-2026" \
  -H "Content-Type: application/json" \
  -d '{"start":"now-1h","end":"now","size":5}'
```

**Expected:** Same JSON as Step 2.

**If connection refused / timeout:** The container cannot reach Django. Try using the host IP instead of the domain:

```bash
docker exec openclaw-openclaw-gateway-1 \
  curl -sS -X POST "https://196.21.5.228/api/openclaw/syslogs/search/" \
  -H "Authorization: Bearer netcare-openclaw-syslog-2026" \
  -H "Content-Type: application/json" \
  -d '{"start":"now-1h","end":"now","size":5}'
```

If the container lacks `curl`, install it first:

```bash
docker exec openclaw-openclaw-gateway-1 apt-get update && \
docker exec openclaw-openclaw-gateway-1 apt-get install -y curl
```

---

## Step 4 — Update OpenClaw TOOLS.md

Add a syslog section to `/root/.openclaw/workspace/TOOLS.md` (below the existing pyATS section):

```markdown
## Syslog Search (Elasticsearch)

**当用户提问涉及历史日志、防火墙拒绝记录、跨设备日志关联、事件时间线重建：必须使用 syslog search API。**

强制规则：
- 必须通过 `exec` 工具执行 `curl` 命令调用 Django API
- 禁止直接连接 Elasticsearch
- 每次查询必须带 `start` 和 `end` 时间范围
- `vendors` 只允许 `cisco` 和 `panw`
- 返回的 JSON 中 `results` 数组包含标准化的日志条目

工具选择：
- 历史日志分析 / 防火墙deny记录 / 跨设备关联 / 时间线重建 → **syslog search**
- 当前接口状态 / 当前路由配置 / ping测试 / 设备本地日志 → **pyATS**
```

Then fix permissions:

```bash
chown 1000:1000 /root/.openclaw/workspace/TOOLS.md
```

---

## Step 5 — Create syslog SKILL.md (optional but recommended)

```bash
mkdir -p /root/.openclaw/workspace/skills/syslog
```

Create `/root/.openclaw/workspace/skills/syslog/SKILL.md` with the curl command template and trigger rules. This teaches OpenClaw the exact command to run when the syslog skill is triggered.

Then fix permissions:

```bash
chown -R 1000:1000 /root/.openclaw/workspace/skills/syslog
```

---

## Step 6 — Restart OpenClaw gateway + reset session

```bash
cd /qytclaw/openclaw && docker compose restart openclaw-gateway
```

Then in Feishu, send:

```
重置会话
```

This clears the old session context so the agent reads the updated TOOLS.md.

---

## Step 7 — End-to-end test

Ask the agent in Feishu or the Web UI:

```
过去2小时有没有防火墙deny记录？
```

or:

```
帮我查一下 10.10.10.5 最近的 syslog 日志
```

**Expected:** The agent triggers the syslog skill, runs curl via exec, gets JSON results from Django, and summarises the findings in Chinese.

---

## Progress Tracker

| Step | Task | Status |
|---|---|---|
| 1 | Restart Django | ✅ |
| 2 | Test API from host | ✅ |
| 3 | Test from OpenClaw container | ✅ (via `https://172.19.11.14`) |
| 4 | Update TOOLS.md | ✅ |
| 5 | Create syslog SKILL.md | ✅ |
| 6 | Restart gateway + reset session | ✅ |
| 7 | End-to-end test | ⬜ |
