import os
import re
import string
import sys
import json
import logging
import textwrap
from pyats.topology import loader
from genie.libs.parser.utils import get_parser
from dotenv import load_dotenv
from typing import Dict, Any
import asyncio
from functools import partial
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PyatsSSEMCPServer")

load_dotenv()
TESTBED_PATH = os.getenv("PYATS_TESTBED_PATH", "/app/testbed.yaml")

if not os.path.exists(TESTBED_PATH):
    logger.critical(f"❌ testbed 文件不存在: {TESTBED_PATH}")
    sys.exit(1)

logger.info(f"✅ 使用 testbed: {TESTBED_PATH}")

HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8765"))

from mcp.server.transport_security import TransportSecuritySettings

# ---------- pyATS 核心函数 ----------

def _get_device(device_name: str):
    testbed = loader.load(TESTBED_PATH)
    device = testbed.devices.get(device_name)
    if not device:
        raise ValueError(f"设备 '{device_name}' 在 testbed 中不存在")
    if not device.is_connected():
        logger.info(f"连接 {device_name}...")
        device.connect(connection_timeout=120, learn_hostname=True, log_stdout=False, mit=True)
        logger.info(f"已连接 {device_name}")
    return device

def _disconnect(device):
    if device and device.is_connected():
        try:
            device.disconnect()
        except Exception as e:
            logger.warning(f"断开 {device.name} 失败: {e}")

def clean_output(output: str) -> str:
    ansi = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ''.join(c for c in ansi.sub('', output) if c in string.printable)

def _list_devices() -> Dict[str, Any]:
    try:
        testbed = loader.load(TESTBED_PATH)
        devices = {}
        for name, dev in testbed.devices.items():
            conn = {}
            if hasattr(dev, 'connections'):
                for cname, cinfo in dev.connections.items():
                    if hasattr(cinfo, 'ip'):
                        conn[cname] = {"ip": str(cinfo.ip), "protocol": getattr(cinfo, 'protocol', 'ssh')}
            devices[name] = {
                "type": getattr(dev, 'type', 'unknown'),
                "os": getattr(dev, 'os', 'unknown'),
                "platform": getattr(dev, 'platform', 'unknown'),
                "connections": conn,
            }
        return {"status": "success", "device_count": len(devices), "devices": devices}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def _execute_show(device_name: str, command: str) -> Dict[str, Any]:
    disallowed = ['|', 'include', 'exclude', 'begin', '>', '<', 'erase', 'reload', 'write', 'copy', 'delete']
    cmd_lower = command.lower().strip()
    if not cmd_lower.startswith("show"):
        return {"status": "error", "error": f"'{command}' 不是 show 命令"}
    for part in cmd_lower.split():
        if part in disallowed:
            return {"status": "error", "error": f"命令包含不允许的词 '{part}'"}
    device = None
    try:
        device = _get_device(device_name)
        try:
            return {"status": "completed", "device": device_name, "output": device.parse(command)}
        except Exception:
            return {"status": "completed_raw", "device": device_name, "output": device.execute(command)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        _disconnect(device)

def _execute_config(device_name: str, config_commands: str) -> Dict[str, Any]:
    if "erase" in config_commands.lower():
        return {"status": "error", "error": "检测到危险命令 (erase)，已拒绝"}
    device = None
    try:
        device = _get_device(device_name)
        cleaned = textwrap.dedent(config_commands.strip())
        output = device.configure(cleaned)
        return {"status": "success", "device": device_name, "output": output}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        _disconnect(device)

def _execute_running_config(device_name: str) -> Dict[str, Any]:
    device = None
    try:
        device = _get_device(device_name)
        device.enable()
        raw = device.execute("show run brief")
        return {"status": "completed_raw", "device": device_name, "output": clean_output(raw)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        _disconnect(device)

def _execute_logging(device_name: str) -> Dict[str, Any]:
    device = None
    try:
        device = _get_device(device_name)
        raw = device.execute("show logging last 250")
        return {"status": "completed_raw", "device": device_name, "output": raw}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        _disconnect(device)

def _execute_ping(device_name: str, command: str) -> Dict[str, Any]:
    if not command.lower().strip().startswith("ping"):
        return {"status": "error", "error": f"'{command}' 不是 ping 命令"}
    device = None
    try:
        device = _get_device(device_name)
        try:
            return {"status": "completed", "device": device_name, "output": device.parse(command)}
        except Exception:
            return {"status": "completed_raw", "device": device_name, "output": device.execute(command)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        _disconnect(device)

def _execute_linux(device_name: str, command: str) -> Dict[str, Any]:
    device = None
    try:
        testbed = loader.load(TESTBED_PATH)
        if device_name not in testbed.devices:
            return {"status": "error", "error": f"设备 '{device_name}' 不存在"}
        device = testbed.devices[device_name]
        if not device.is_connected():
            device.connect()
        if ">" in command or "|" in command:
            command = f'sh -c "{command}"'
        try:
            if get_parser(command, device):
                output = device.parse(command)
            else:
                raise ValueError()
        except Exception:
            output = device.execute(command)
        return {"status": "completed", "device": device_name, "output": output}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if device and device.is_connected():
            try:
                device.disconnect()
            except Exception:
                pass

# ---------- MCP 工具注册 ----------

mcp = FastMCP(
    "pyATS Network Automation Server",
    host=HOST,
    port=PORT,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    ),
)

@mcp.tool()
async def pyats_list_devices() -> str:
    """列出 testbed 中所有可用网络设备及连接信息，无需任何参数。"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _list_devices)
    return json.dumps(result, indent=2)

@mcp.tool()
async def pyats_run_show_command(device_name: str, command: str) -> str:
    """
    在 Cisco IOS/NX-OS 设备上执行 show 命令。
    Args:
        device_name: testbed 中的设备名
        command: show 命令，如 'show ip interface brief'
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(_execute_show, device_name, command))
    return json.dumps(result, indent=2)

@mcp.tool()
async def pyats_configure_device(device_name: str, config_commands: str) -> str:
    """
    向设备下发配置命令（多行用 \\n 分隔）。
    Args:
        device_name: testbed 中的设备名
        config_commands: 配置命令
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(_execute_config, device_name, config_commands))
    return json.dumps(result, indent=2)

@mcp.tool()
async def pyats_show_running_config(device_name: str) -> str:
    """
    获取设备 running configuration。
    Args:
        device_name: testbed 中的设备名
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(_execute_running_config, device_name))
    return json.dumps(result, indent=2)

@mcp.tool()
async def pyats_show_logging(device_name: str) -> str:
    """
    获取设备最近系统日志。
    Args:
        device_name: testbed 中的设备名
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(_execute_logging, device_name))
    return json.dumps(result, indent=2)

@mcp.tool()
async def pyats_ping_from_network_device(device_name: str, command: str) -> str:
    """
    从设备发起 ping 测试。
    Args:
        device_name: testbed 中的设备名
        command: ping 命令，如 'ping 196.21.5.212'
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(_execute_ping, device_name, command))
    return json.dumps(result, indent=2)

@mcp.tool()
async def pyats_run_linux_command(device_name: str, command: str) -> str:
    """
    在 Linux 设备上执行命令。
    Args:
        device_name: testbed 中的 Linux 设备名
        command: Linux 命令，如 'ifconfig'
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, partial(_execute_linux, device_name, command))
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    logger.info(f"🚀 pyATS SSE MCP Server 启动 → http://{HOST}:{PORT}/sse")
    mcp.run(transport="sse")
