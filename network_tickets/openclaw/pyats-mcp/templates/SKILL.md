---
name: pyats
description: "Network device automation via Cisco pyATS/Genie. 默认中文回复。Use when user asks to: list devices, run show commands, check interface status, view routing tables, check logs, apply configuration, ping between devices, get running config, or check traffic counters. MUST call the exec tool immediately; do not answer from memory. If tool fails, return tool error/output. Do not persistently record device/interface/IP/counter data."
metadata:
  { "openclaw": { "emoji": "🌐" } }
---

# pyATS Network Automation Skill

Interact with Cisco IOS-XE devices via pyATS MCP Server.

## How to Use

Use the `exec` tool to run these commands. Each call takes 15-30 seconds (SSH to device).

### List all devices

```bash
npx --yes mcporter@latest call http://pyats-mcp:8765/sse pyats_list_devices --allow-http --output json
```

### Show interface status (choose device + command)

```bash
npx --yes mcporter@latest call http://pyats-mcp:8765/sse pyats_run_show_command device_name=<DEVICE_NAME> "command=show ip interface brief" --allow-http --output json
```

### Show routing table

```bash
npx --yes mcporter@latest call http://pyats-mcp:8765/sse pyats_run_show_command device_name=<DEVICE_NAME> "command=show ip route" --allow-http --output json
```

### Show running config

```bash
npx --yes mcporter@latest call http://pyats-mcp:8765/sse pyats_show_running_config device_name=<DEVICE_NAME> --allow-http --output json
```

### Show system logs

```bash
npx --yes mcporter@latest call http://pyats-mcp:8765/sse pyats_show_logging device_name=<DEVICE_NAME> --allow-http --output json
```

### Ping from device

```bash
npx --yes mcporter@latest call http://pyats-mcp:8765/sse pyats_ping_from_network_device device_name=<DEVICE_NAME> "command=ping <TARGET_IP>" --allow-http --output json
```

### Apply configuration

```bash
npx --yes mcporter@latest call http://pyats-mcp:8765/sse pyats_configure_device device_name=<DEVICE_NAME> "config_commands=<CONFIG_LINES>" --allow-http --output json
```

## Rules

- When user asks about devices, interface, routing, config, logs, or ping → **immediately run `pyats_list_devices` first via `exec`, then run the relevant command**
- **NEVER ask the user for device names, IP addresses, or testbed config** — run `pyats_list_devices` to discover them
- **NEVER use `read`/`cat` to look for `testbed.yaml` in workspace**
- **NEVER say "I don't have the device list"** — that's what `pyats_list_devices` is for
- Replace `<DEVICE_NAME>` with values from `pyats_list_devices` output
- If a command fails, try up to 5 different commands before giving up
- Always return raw tool output on failure, never invent reasons
