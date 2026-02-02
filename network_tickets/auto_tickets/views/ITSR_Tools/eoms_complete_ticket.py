#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EOMS 自动关单脚本
自动获取待处理工单列表，批量执行关单操作

功能:
1. 使用 Playwright 无头模式账号密码登录
2. 获取待处理工单列表
3. 批量执行关单操作
"""

import json
import re
import asyncio
import os
from datetime import datetime
from urllib.parse import urlencode, quote
from playwright.async_api import async_playwright, Page
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================
# 配置
# ============================================================
DEFAULT_CONFIG = {
    "username": "p7869",
    "password": "Ericsson_5",
}


class EOmsCompleteClient:
    """EOMS 关单客户端"""
    
    STORAGE_STATE_FILE = "eoms_complete_auth_state.json"
    
    def __init__(self, username: str = None, password: str = None, storage_state_path: str = None):
        """
        初始化 EOMS 关单客户端
        
        参数:
            username: 登录用户名（工号）
            password: 登录密码
            storage_state_path: 登录状态缓存文件路径
        """
        self.base_url = "https://eoms2.cmhktry.com/x5"
        self.cookies = {}
        self.headers = {}
        
        # 登录凭证
        self.username = username or DEFAULT_CONFIG["username"]
        self.password = password or DEFAULT_CONFIG["password"]
        
        # 登录状态缓存文件
        self.storage_state_path = storage_state_path or self.STORAGE_STATE_FILE
    
    async def login(self, headless: bool = True, use_cache: bool = True) -> bool:
        """
        使用 Playwright 登录并获取 Cookies
        
        参数:
            headless: 是否无头模式
            use_cache: 是否使用缓存的登录状态
        
        返回:
            bool: 登录是否成功
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            
            # 检查缓存
            storage_state = None
            if use_cache and os.path.exists(self.storage_state_path):
                print(f"📂 发现缓存的登录状态: {self.storage_state_path}")
                storage_state = self.storage_state_path
            
            context = await browser.new_context(
                ignore_https_errors=True,
                viewport={"width": 1280, "height": 800},
                storage_state=storage_state,
            )
            page = await context.new_page()
            
            # 监听请求，捕获 headers
            captured_headers = {}
            
            async def capture_request(request):
                if "eoms2.cmhktry.com" in request.url:
                    captured_headers.update(request.headers)
            
            page.on("request", capture_request)
            
            # 访问首页
            print(f"🌐 正在打开: {self.base_url}")
            await page.goto(self.base_url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # 检查是否需要登录
            current_url = page.url
            need_login = "ncas.cmhktry.com" in current_url or "cas" in current_url.lower()
            
            if need_login:
                if storage_state:
                    print("⚠️ 缓存的登录状态已过期，需要重新登录")
                print(f"🔐 正在自动登录...")
                
                try:
                    await self._auto_login(page, timeout_seconds=30)
                    print("✅ 登录成功!")
                except Exception as e:
                    print(f"❌ 登录失败: {e}")
                    await browser.close()
                    return False
            else:
                print("✅ 使用缓存的登录状态")
            
            # 等待页面加载
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # 获取 Cookies
            cookies_list = await context.cookies()
            self.cookies = {c["name"]: c["value"] for c in cookies_list}
            self.headers = captured_headers
            
            print(f"📦 捕获到 {len(self.cookies)} 个 Cookies")
            
            # 保存登录状态
            await context.storage_state(path=self.storage_state_path)
            print(f"💾 登录状态已缓存")
            
            await browser.close()
            return True
    
    async def _auto_login(self, page: Page, timeout_seconds: int = 30):
        """自动填写账号密码并登录"""
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)
        
        # 定位用户名输入框
        username_selectors = [
            'input#username', 'input[name="username"]',
            'input[type="text"]:first-of-type',
        ]
        username_input = None
        for selector in username_selectors:
            try:
                username_input = await page.wait_for_selector(selector, timeout=3000)
                if username_input:
                    break
            except:
                continue
        
        if not username_input:
            raise Exception("未找到用户名输入框")
        
        # 定位密码输入框
        password_selectors = [
            'input#password', 'input[name="password"]',
            'input[type="password"]',
        ]
        password_input = None
        for selector in password_selectors:
            try:
                password_input = await page.wait_for_selector(selector, timeout=3000)
                if password_input:
                    break
            except:
                continue
        
        if not password_input:
            raise Exception("未找到密码输入框")
        
        # 填写表单
        await username_input.fill("")
        await username_input.type(self.username, delay=50)
        await password_input.fill("")
        await password_input.type(self.password, delay=50)
        
        await asyncio.sleep(0.5)
        
        # 提交登录
        submit_selectors = [
            'button[type="submit"]', 'input[type="submit"]',
            'button:has-text("登录")', 'button:has-text("Login")',
        ]
        submit_button = None
        for selector in submit_selectors:
            try:
                submit_button = await page.wait_for_selector(selector, timeout=2000)
                if submit_button:
                    break
            except:
                continue
        
        if submit_button:
            await submit_button.click()
        else:
            await password_input.press("Enter")
        
        # 等待登录完成
        start_time = asyncio.get_event_loop().time()
        while True:
            current_time = asyncio.get_event_loop().time()
            if (current_time - start_time) > timeout_seconds:
                raise TimeoutError("登录超时")
            
            if "eoms2.cmhktry.com" in page.url:
                if "/login" not in page.url.lower() and "cas" not in page.url.lower():
                    await page.wait_for_load_state("networkidle")
                    return
            
            await asyncio.sleep(0.5)
    
    def get_pending_tasks(self) -> list:
        """
        获取待处理工单列表
        
        请求 URL: GET /x5/office/receivedProcess/pendingJson
        
        返回:
            list: 待处理工单列表
        """
        url = f"{self.base_url}/office/receivedProcess/pendingJson"
        
        headers = {
            "User-Agent": self.headers.get("user-agent", "Mozilla/5.0"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        print(f"\n📡 获取待处理工单列表...")
        print(f"   URL: {url}")
        
        try:
            response = session.get(url, headers=headers, verify=False)
            
            if response.status_code != 200:
                print(f"❌ 请求失败，状态码: {response.status_code}")
                return []
            
            data = response.json()
            rows = data.get("rows", [])
            total = data.get("total", 0)
            
            print(f"✅ 获取成功，共 {total} 个待处理工单")
            
            # 打印完整字段信息用于调试
            for i, row in enumerate(rows[:3]):  # 只打印前3个
                print(f"   [{i+1}] {row.get('subject', 'N/A')}")
                print(f"       id: {row.get('id')}, procDefKey: {row.get('procDefKey')}")
                print(f"       status: {row.get('status')}, creator: {row.get('creator')}")
                # 打印所有字段名，帮助发现可能的 taskId 字段
                print(f"       所有字段: {list(row.keys())}")
            
            return rows
            
        except Exception as e:
            print(f"❌ 获取待处理工单失败: {e}")
            return []
    
    def get_task_approve_info(self, inst_id: str) -> dict:
        """
        获取任务审批信息
        
        请求 URL: GET /x5/flow/task/taskApprove?id=xxx
        
        参数:
            inst_id: 实例 ID (从 pendingJson 的 id 字段获取)
        
        返回:
            dict: 任务审批信息，包含 taskId 等
        """
        url = f"{self.base_url}/flow/task/taskApprove"
        
        headers = {
            "User-Agent": self.headers.get("user-agent", "Mozilla/5.0"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        
        params = {"id": inst_id}
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        try:
            print(f"   📡 获取任务审批信息: {url}?id={inst_id}")
            response = session.get(url, params=params, headers=headers, verify=False)
            print(f"   📥 响应状态: {response.status_code}")
            print(f"   📥 响应长度: {len(response.text)} 字符")
            
            if response.status_code == 200:
                # 这可能返回 HTML 页面，需要从中提取 taskId
                # 或者返回 JSON
                content_type = response.headers.get("Content-Type", "")
                print(f"   📥 Content-Type: {content_type}")
                
                if "json" in content_type:
                    data = response.json()
                    print(f"   📥 JSON 响应: {json.dumps(data, ensure_ascii=False)[:500]}...")
                    return data
                else:
                    # HTML 响应，尝试从中提取 taskId
                    html = response.text
                    print(f"   📥 HTML 响应前 500 字符: {html[:500]}...")
                    
                    # 尝试在 HTML 中查找 taskId
                    import re
                    # 查找类似 taskId=xxx 或 "taskId":"xxx" 的模式
                    patterns = [
                        r'taskId["\']?\s*[:=]\s*["\']?(\d+)',
                        r'"taskId"\s*:\s*"?(\d+)"?',
                        r"'taskId'\s*:\s*'?(\d+)'?",
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html)
                        if match:
                            task_id = match.group(1)
                            print(f"   ✅ 从 HTML 中提取到 taskId: {task_id}")
                            return {"taskId": task_id}
                    
                    print(f"   ⚠️ 未能从 HTML 中提取 taskId")
            else:
                print(f"   ❌ 响应内容: {response.text[:300]}")
            return {}
            
        except Exception as e:
            print(f"   ❌ 获取任务审批信息失败: {e}")
            return {}
    
    def get_task_form_data(self, task_id: str) -> dict:
        """
        获取工单的表单数据（用于关单）
        
        请求 URL: GET /x5/flow/task/taskDetail?taskId={taskId}
        
        参数:
            task_id: 任务 ID
        
        返回:
            dict: 表单数据，结构为 {"data": {"instId": "xxx", "ServiceConfig": {...}}}
        """
        url = f"{self.base_url}/flow/task/taskDetail"
        
        headers = {
            "User-Agent": self.headers.get("user-agent", "Mozilla/5.0"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }
        
        params = {
            "taskId": task_id,
        }
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        try:
            print(f"   📡 获取表单数据: {url}?taskId={task_id}")
            response = session.get(url, params=params, headers=headers, verify=False)
            print(f"   📥 响应状态: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # taskDetail 返回的结构: {"result": true, "data": {"instId": "xxx", "ServiceConfig": {...}}, ...}
                if data.get("result") and data.get("data"):
                    print(f"   ✅ 获取表单数据成功")
                    inst_id = data.get("data", {}).get("instId", "")
                    service_config = data.get("data", {}).get("ServiceConfig", {})
                    print(f"   📋 instId: {inst_id}")
                    print(f"   📋 ServiceConfig 字段数: {len(service_config)}")
                    return data
                else:
                    print(f"   ⚠️ 响应中没有有效数据: {json.dumps(data, ensure_ascii=False)[:300]}...")
            else:
                print(f"   ❌ 响应内容: {response.text[:200]}")
            return {}
            
        except Exception as e:
            print(f"   ❌ 获取表单数据失败: {e}")
            return {}
    
    def complete_task(
        self,
        task_id: str,
        inst_id: str,
        service_config: dict,
        bpm_form_id: str = "ServiceConfigurationTicket",
        action_name: str = "agree",
        opinion: str = "同意",
    ) -> dict:
        """
        完成/关闭工单
        
        请求 URL: POST /x5/flow/task/complete
        
        参数:
            task_id: 任务 ID
            inst_id: 实例 ID
            service_config: ServiceConfig 数据
            bpm_form_id: 表单 ID
            action_name: 操作名称 (agree)
            opinion: 审批意见
        
        返回:
            dict: API 响应
        """
        url = f"{self.base_url}/flow/task/complete"
        
        headers = {
            "User-Agent": self.headers.get("user-agent", "Mozilla/5.0"),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://eoms2.cmhktry.com",
        }
        
        # 构建 data 字段
        data_content = {
            "instId": inst_id,
            "ServiceConfig": service_config,
        }
        
        # 构建 Form Data
        form_data = {
            "taskId": task_id,
            "actionName": action_name,
            "opinion": opinion,
            "bpmFormId": bpm_form_id,
            "data": json.dumps(data_content, ensure_ascii=False),
            "nodeUsers": json.dumps([{"executors": []}]),
        }
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        print(f"\n📤 正在关闭工单...")
        print(f"   taskId: {task_id}")
        print(f"   instId: {inst_id}")
        print(f"   actionName: {action_name}")
        
        try:
            response = session.post(url, data=form_data, headers=headers, verify=False)
            
            print(f"📥 响应状态码: {response.status_code}")
            print(f"📥 响应内容: {response.text[:200]}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("result") == 1:
                    print(f"✅ 工单关闭成功: {result.get('message')}")
                else:
                    print(f"⚠️ 工单关闭失败: {result}")
                return result
            
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
        except Exception as e:
            print(f"❌ 关闭工单失败: {e}")
            return {"success": False, "error": str(e)}
    
    def close_ticket_by_inst_id(
        self,
        inst_id: str,
        opinion: str = "同意",
    ) -> dict:
        """
        根据 instId 关闭指定工单（集中函数）
        
        流程:
        1. 调用 /x5/flow/task/taskApprove?id={instId} 获取 taskId
        2. 调用 /x5/flow/instance/getFormAndBO 获取 ServiceConfig
        3. 调用 /x5/flow/task/complete 执行关单
        
        参数:
            inst_id: 实例 ID（从 pendingJson 获取）
            opinion: 审批意见，默认 "同意"
        
        返回:
            dict: {
                "success": bool,
                "instId": str,
                "taskId": str,
                "message": str,
                "response": dict
            }
        """
        print(f"\n{'='*50}")
        print(f"🔄 开始关闭工单: instId={inst_id}")
        print(f"{'='*50}")
        
        # 步骤 1: 通过 taskApprove 获取 taskId
        approve_info = self.get_task_approve_info(inst_id)
        task_id = approve_info.get("taskId")
        
        if not task_id:
            return {
                "success": False,
                "instId": inst_id,
                "taskId": None,
                "message": "未能从 taskApprove 获取 taskId",
                "response": approve_info,
            }
        
        print(f"   ✅ 获取到 taskId: {task_id}")
        
        # 步骤 2: 获取表单数据
        form_data = self.get_task_form_data(task_id)
        
        if not form_data:
            return {
                "success": False,
                "instId": inst_id,
                "taskId": task_id,
                "message": "未能获取表单数据",
                "response": {},
            }
        
        # 提取 ServiceConfig
        bo_data = form_data.get("data", {})
        service_config = bo_data.get("ServiceConfig", {})
        
        if not service_config:
            # 尝试直接使用 bo_data
            service_config = bo_data
            print(f"   ⚠️ ServiceConfig 为空，使用 bo_data 替代")
        
        print(f"   ✅ 获取到 ServiceConfig")
        
        # 步骤 3: 执行关单
        result = self.complete_task(
            task_id=task_id,
            inst_id=inst_id,
            service_config=service_config,
            bpm_form_id="ServiceConfigurationTicket",
            opinion=opinion,
        )
        
        success = result.get("result") == 1
        
        return {
            "success": success,
            "instId": inst_id,
            "taskId": task_id,
            "message": result.get("message", "unknown"),
            "response": result,
        }
    
    def get_my_pending_tasks(self) -> list:
        """
        获取我的待处理工单列表（已收流程待办）
        
        请求 URL: GET /x5/office/receivedProcess/pendingJson
        
        返回格式:
        {
            "pageResult": {...},
            "rows": [
                {
                    "id": "10000250957699",           # 工单 ID（用于关单时作为 taskId）
                    "procDefKey": "ServiceConfigurationTicket",
                    "procDefName": "Service Configuration Ticket",
                    "subject": "10000250957699-xxx",
                    "status": "draft",
                    "creator": "Chris TAO Yuxuan",
                    ...
                }
            ],
            "total": 6
        }
        
        返回:
            list: 待处理工单列表
        """
        url = f"{self.base_url}/office/receivedProcess/pendingJson"
        
        headers = {
            "User-Agent": self.headers.get("user-agent", "Mozilla/5.0"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        print(f"\n📡 获取待处理工单列表...")
        print(f"   URL: {url}")
        
        try:
            response = session.get(url, headers=headers, verify=False)
            
            if response.status_code != 200:
                print(f"❌ 请求失败，状态码: {response.status_code}")
                return []
            
            data = response.json()
            rows = data.get("rows", [])
            total = data.get("total", 0)
            
            print(f"✅ 获取成功，共 {total} 个待处理工单")
            
            # 打印工单列表
            for i, task in enumerate(rows[:10]):  # 只显示前10个
                subject = task.get('subject', 'N/A')
                if len(subject) > 50:
                    subject = subject[:50] + "..."
                print(f"   [{i+1}] {subject}")
                print(f"       id: {task.get('id')}, procDefKey: {task.get('procDefKey')}")
                print(f"       status: {task.get('status')}, creator: {task.get('creator')}")
            
            return rows
            
        except Exception as e:
            print(f"❌ 获取待处理工单失败: {e}")
            return []


async def complete_all_pending_tasks(
    username: str = None,
    password: str = None,
    opinion: str = "同意",
    headless: bool = True,
) -> dict:
    """
    获取并关闭所有待处理的 Service Configuration Ticket
    
    注意：只会关闭 Service Configuration Ticket 类型的工单，
    其他类型的工单会被自动跳过。
    
    使用 /x5/office/receivedProcess/pendingJson 获取待处理工单列表，
    然后对每个 Service Configuration Ticket 执行关单操作。
    
    参数:
        username: 登录用户名
        password: 登录密码
        opinion: 审批意见，默认 "同意"
        headless: 是否无头模式，默认 True
    
    返回:
        dict: {
            "success": bool,
            "completed": int,  # 成功关闭的数量
            "failed": int,     # 失败的数量
            "results": list,   # 详细结果
        }
    """
    print("\n" + "=" * 60)
    print("EOMS 自动关单 (Service Configuration Ticket)")
    print("=" * 60)
    
    client = EOmsCompleteClient(username=username, password=password)
    
    # 1. 登录
    success = await client.login(headless=headless)
    if not success:
        return {"success": False, "error": "登录失败"}
    
    # 2. 获取待处理工单（使用 pendingJson）
    tasks = client.get_my_pending_tasks()
    
    if not tasks:
        print("ℹ️ 没有待处理工单")
        return {"success": True, "completed": 0, "message": "没有待处理工单"}
    
    # 3. 只处理 Service Configuration Ticket 类型的工单
    # 强制过滤，只关闭 ServiceConfigurationTicket 类型
    SERVICE_CONFIG_TICKET_KEY = "ServiceConfigurationTicket"
    
    original_count = len(tasks)
    tasks = [t for t in tasks if t.get("procDefKey") == SERVICE_CONFIG_TICKET_KEY]
    
    print(f"📋 总工单数: {original_count}")
    print(f"📋 Service Configuration Ticket 数量: {len(tasks)}")
    
    if original_count > len(tasks):
        skipped = original_count - len(tasks)
        print(f"⏭️ 跳过 {skipped} 个非 Service Configuration Ticket 工单")
    
    if not tasks:
        print("ℹ️ 没有 Service Configuration Ticket 类型的工单")
        return {"success": True, "completed": 0, "message": "没有 Service Configuration Ticket 工单"}
    
    # 4. 执行关单
    results = []
    for i, task in enumerate(tasks):
        # pendingJson 返回的字段：
        # - id: 实例 ID (instId)，注意：不是 taskId！
        # - procDefKey: 流程定义 Key（用作 bpmFormId）
        # - subject: 工单标题
        # - status: 状态
        # - creator: 创建人
        inst_id = task.get("id")  # 这是实例 ID，不是任务 ID
        subject = task.get("subject", "N/A")
        proc_def_key = task.get("procDefKey", "")
        status = task.get("status", "unknown")
        creator = task.get("creator", "N/A")
        
        # 再次验证是 Service Configuration Ticket（双重保险）
        if proc_def_key != SERVICE_CONFIG_TICKET_KEY:
            print(f"\n[{i+1}/{len(tasks)}] ⏭️ 跳过非 Service Configuration Ticket:")
            print(f"   instId: {inst_id}, procDefKey: {proc_def_key}")
            results.append({"instId": inst_id, "status": "skipped (not ServiceConfigurationTicket)"})
            continue
        
        print(f"\n[{i+1}/{len(tasks)}] 处理 Service Configuration Ticket:")
        print(f"   instId (from pendingJson): {inst_id}")
        print(f"   subject: {subject[:50]}..." if len(subject) > 50 else f"   subject: {subject}")
        print(f"   status: {status}")
        print(f"   creator: {creator}")
        
        # 步骤 1: 通过 taskApprove 获取 taskId
        approve_info = client.get_task_approve_info(inst_id)
        
        task_id = approve_info.get("taskId")
        if not task_id:
            print(f"   ⚠️ 未能获取 taskId，跳过")
            results.append({"instId": inst_id, "status": "skipped (no taskId found)"})
            continue
        
        print(f"   ✅ 找到 taskId: {task_id}")
        
        # 步骤 2: 获取表单数据
        form_data = client.get_task_form_data(task_id)
        
        if not form_data:
            print("   ⚠️ 无法获取表单数据，跳过")
            results.append({"instId": inst_id, "taskId": task_id, "status": "skipped (no form data)"})
            continue
        
        # 提取 ServiceConfig
        bo_data = form_data.get("data", {})
        service_config = bo_data.get("ServiceConfig", {})
        
        if not service_config:
            # 尝试从其他位置获取
            service_config = bo_data
        
        # 执行关单
        result = client.complete_task(
            task_id=task_id,
            inst_id=inst_id,  # pendingJson 的 id 就是 instId
            service_config=service_config,
            bpm_form_id=SERVICE_CONFIG_TICKET_KEY,
            opinion=opinion,
        )
        
        if result.get("result") == 1:
            print(f"   ✅ 关单成功!")
        else:
            print(f"   ❌ 关单失败: {result.get('message', 'unknown error')}")
        
        results.append({
            "instId": inst_id,
            "taskId": task_id,
            "status": "success" if result.get("result") == 1 else "failed",
            "response": result,
        })
        
        # 避免请求过快
        await asyncio.sleep(1)
    
    # 5. 统计结果
    success_count = len([r for r in results if r.get("status") == "success"])
    failed_count = len([r for r in results if r.get("status") == "failed"])
    
    print("\n" + "=" * 60)
    print(f"📊 执行完成:")
    print(f"   成功: {success_count}")
    print(f"   失败: {failed_count}")
    print(f"   跳过: {len(results) - success_count - failed_count}")
    print("=" * 60)
    
    return {
        "success": True,
        "completed": success_count,
        "failed": failed_count,
        "results": results,
    }


def complete_all_pending_tasks_sync(
    opinion: str = "同意",
    headless: bool = True,
    **kwargs,
) -> dict:
    """
    关闭所有待处理的 Service Configuration Ticket（同步版本，方便其他模块调用）
    
    注意：只会关闭 Service Configuration Ticket 类型的工单，
    其他类型的工单会被自动跳过。
    
    参数:
        opinion: 审批意见，默认 "同意"
        headless: 是否无头模式，默认 True
        **kwargs: 其他参数（username, password 等）
    
    返回:
        dict: {
            "success": bool,
            "completed": int,  # 成功关闭的数量
            "failed": int,     # 失败的数量
            "results": list,   # 详细结果
        }
    
    示例（从其他模块调用）:
        from eoms_complete_ticket import complete_all_pending_tasks_sync
        
        # 最简调用 - 关闭所有 Service Configuration Ticket
        result = complete_all_pending_tasks_sync()
        
        # 自定义审批意见
        result = complete_all_pending_tasks_sync(opinion="已处理")
        
        # 查看结果
        print(f"成功: {result['completed']}, 失败: {result['failed']}")
    """
    return asyncio.run(complete_all_pending_tasks(
        opinion=opinion,
        headless=headless,
        **kwargs,
    ))


async def close_ticket(
    inst_id: str,
    opinion: str = "同意",
    username: str = None,
    password: str = None,
    headless: bool = True,
) -> dict:
    """
    根据 instId 关闭指定工单
    
    参数:
        inst_id: 实例 ID（必填）
        opinion: 审批意见，默认 "同意"
        username: 登录用户名（可选，默认使用 DEFAULT_CONFIG）
        password: 登录密码（可选，默认使用 DEFAULT_CONFIG）
        headless: 是否无头模式，默认 True
    
    返回:
        dict: {
            "success": bool,
            "instId": str,
            "taskId": str,
            "message": str,
            "response": dict
        }
    """
    print(f"\n{'='*60}")
    print(f"EOMS 关闭指定工单: instId={inst_id}")
    print(f"{'='*60}")
    
    client = EOmsCompleteClient(username=username, password=password)
    
    # 登录
    success = await client.login(headless=headless)
    if not success:
        return {
            "success": False,
            "instId": inst_id,
            "taskId": None,
            "message": "登录失败",
            "response": {},
        }
    
    # 关闭工单
    result = client.close_ticket_by_inst_id(inst_id=inst_id, opinion=opinion)
    
    return result


def close_ticket_sync(
    inst_id: str,
    opinion: str = "同意",
    **kwargs,
) -> dict:
    """
    根据 instId 关闭指定工单（同步版本，方便其他模块调用）
    
    参数:
        inst_id: 实例 ID（必填）
        opinion: 审批意见，默认 "同意"
        **kwargs: 其他参数（username, password, headless 等）
    
    返回:
        dict: {
            "success": bool,
            "instId": str,
            "taskId": str,
            "message": str,
            "response": dict
        }
    
    示例（从其他模块调用）:
        from eoms_complete_ticket import close_ticket_sync
        
        # 关闭指定工单
        result = close_ticket_sync(inst_id="10000252091465")
        
        # 自定义审批意见
        result = close_ticket_sync(inst_id="10000252091465", opinion="已处理")
        
        # 查看结果
        if result["success"]:
            print(f"关单成功! taskId: {result['taskId']}")
        else:
            print(f"关单失败: {result['message']}")
    """
    return asyncio.run(close_ticket(
        inst_id=inst_id,
        opinion=opinion,
        **kwargs,
    ))


async def main():
    """示例用法 - 直接运行关单（只关闭 Service Configuration Ticket）"""
    result = await complete_all_pending_tasks(
        opinion="同意",
        headless=True,
    )
    
    print(f"\n📊 结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())

