#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EOMS 自动化脚本
自动获取登录后的请求头和 Cookies，然后发送 POST 请求
支持账号密码自动登录（含验证码处理）
"""

import json
import os
import re
import asyncio
import tempfile
import uuid
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Page


class EOmsClient:
    """EOMS 客户端"""
    
    def __init__(self, username: str = "", password: str = ""):
        """
        初始化 EOMS 客户端
        
        参数:
            username: 登录用户名（工号）
            password: 登录密码
        """
        self.base_url = "https://eoms2.cmhktry.com/x5"
        self.cas_login_url = "https://ncas.cmhktry.com/cas/login"
        self.home_url = "https://eoms2.cmhktry.com/x5/main/home"
        self.cookies = {}
        self.headers = {}
        self.home_headers = {}
        self.captured_requests = []
        self.def_id = ""
        
        self.username = username
        self.password = password

    async def _finish_logged_in_session(self, context, page, browser, captured_headers, home_headers):
        """Navigate to home, capture cookies/headers, close browser, fetch defId."""
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        current_url = page.url
        if "/main/home" not in current_url:
            print(f"🌐 正在跳转到首页...")
            await page.goto(self.home_url, wait_until="networkidle")
            await asyncio.sleep(2)

        cookies_list = await context.cookies()
        self.cookies = {c["name"]: c["value"] for c in cookies_list}
        self.headers = captured_headers
        self.home_headers = home_headers

        print(f"\n📦 捕获到 {len(self.cookies)} 个 Cookies")
        print(f"📦 捕获到 {len(self.headers)} 个 Headers (全部)")
        print(f"📦 捕获到 {len(self.home_headers)} 个 Headers (/main/home)")
        print(f"📦 捕获到 {len(self.captured_requests)} 个请求")

        await browser.close()

        print(f"\n🔍 正在通过 API 获取 defId...")
        def_id = self._extract_def_id_from_api()
        if def_id:
            self.def_id = def_id
            print(f"✅ 成功获取 defId: {def_id}")
        else:
            print("⚠️ 未能获取 defId，请检查 API 响应")

        return {
            "cookies": self.cookies,
            "headers": self.headers,
            "home_headers": self.home_headers,
            "requests": self.captured_requests,
            "def_id": self.def_id,
        }
    
    async def login_and_capture_headers(
        self,
        headless: bool = True,
        timeout_seconds: int = 30,
        captcha_code: str = "",
        captcha_code_provider=None,
        resume_state_path: str = None,
    ) -> dict:
        """
        自动登录并捕获请求头和 Cookies，获取 defId
        每次调用都会执行完整的登录流程。
        
        参数:
            headless: 是否无头模式（默认 True，不显示浏览器）
            timeout_seconds: 登录超时时间（秒）
            captcha_code: 验证码（可选，检测到验证码时使用）
            captcha_code_provider: 验证码提供函数（可选），
                支持 sync/async callable，签名示例: lambda: "123456"
            resume_state_path: Playwright storage_state JSON（短信第二步恢复同一会话）
        
        返回:
            包含 cookies, headers, home_headers, def_id 的字典；
            若 need_captcha 则可能含 resume_token（用于第二步请求）。
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)

            init_storage = None
            if resume_state_path and os.path.isfile(resume_state_path):
                init_storage = resume_state_path

            context = await browser.new_context(
                ignore_https_errors=True,
                viewport={"width": 1280, "height": 800},
                storage_state=init_storage,
            )
            page = await context.new_page()
            
            # 监听所有请求，捕获请求头
            captured_headers = {}
            home_headers = {}
            
            async def capture_request(request):
                # 捕获对 eoms2 的请求
                if "eoms2.cmhktry.com" in request.url:
                    req_info = {
                        "url": request.url,
                        "method": request.method,
                        "headers": dict(request.headers),
                    }
                    self.captured_requests.append(req_info)
                    # 更新捕获的 headers
                    captured_headers.update(request.headers)
                    
                    # 特别关注 /main/home 的请求头
                    if "/main/home" in request.url or "/x5/main" in request.url:
                        home_headers.update(request.headers)
                        print(f"📍 捕获到 home 请求: {request.url}")
            
            page.on("request", capture_request)

            # ----- 恢复会话：提交短信验证码后继续开单 -----
            if init_storage:
                print("📂 恢复 CAS/EOMS 会话（短信验证码第二步）...")
                await page.goto(self.base_url, wait_until="networkidle")
                await asyncio.sleep(2)
                if not (captcha_code or "").strip():
                    await browser.close()
                    return {
                        "success": False,
                        "need_captcha": True,
                        "message": "恢复会话需要短信验证码",
                    }
                if await self._is_captcha_required(page):
                    login_result = await self._handle_captcha_flow(
                        page,
                        captcha_code=captcha_code,
                        captcha_code_provider=captcha_code_provider,
                    )
                    if login_result.get("need_captcha"):
                        token = str(uuid.uuid4())
                        resume_path = os.path.join(tempfile.gettempdir(), f"eoms_cas_resume_{token}.json")
                        await context.storage_state(path=resume_path)
                        login_result = dict(login_result)
                        login_result["resume_token"] = token
                        await browser.close()
                        return login_result
                    if not login_result.get("success"):
                        await browser.close()
                        return {}
                return await self._finish_logged_in_session(
                    context, page, browser, captured_headers, home_headers
                )
            
            # 访问首页
            print(f"🌐 正在打开: {self.base_url}")
            await page.goto(self.base_url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # 检查是否需要登录（是否跳转到了 CAS 登录页）
            current_url = page.url
            need_login = "ncas.cmhktry.com" in current_url or "cas" in current_url.lower()
            
            if need_login:
                print(f"✅ 已跳转到 CAS 登录页: {current_url[:60]}...")
                
                if not self.username or not self.password:
                    print("❌ 错误: 需要登录但未提供用户名或密码!")
                    await browser.close()
                    return {}
                
                try:
                    login_result = await self._auto_login(
                        page,
                        timeout_seconds=timeout_seconds,
                        captcha_code=captcha_code,
                        captcha_code_provider=captcha_code_provider,
                    )
                    if login_result.get("need_captcha"):
                        token = str(uuid.uuid4())
                        resume_path = os.path.join(tempfile.gettempdir(), f"eoms_cas_resume_{token}.json")
                        await context.storage_state(path=resume_path)
                        login_result = dict(login_result)
                        login_result["resume_token"] = token
                        await browser.close()
                        return login_result
                    print("✅ CAS 登录成功，已返回 EOMS!")
                except Exception as e:
                    print(f"❌ 自动登录失败: {e}")
                    await browser.close()
                    return {}
            
            return await self._finish_logged_in_session(
                context, page, browser, captured_headers, home_headers
            )
    
    async def _auto_login(
        self,
        page: Page,
        timeout_seconds: int = 30,
        captcha_code: str = "",
        captcha_code_provider=None,
    ):
        """
        自动填写账号密码并登录（无验证码模式）
        增强点：自动检测登录错误和验证码页面
        
        CAS 登录页面表单:
        - 用户名输入框: id="username" 或 name="username"
        - 密码输入框: id="password" 或 name="password"
        - 登录按钮: type="submit" 或包含 "登录/Login" 文字
        
        参数:
            page: Playwright Page 对象
            timeout_seconds: 登录超时时间（秒）
        """
        print(f"🔐 正在自动登录...")
        print(f"   用户名: {self.username}")
        print(f"   密码: {'*' * len(self.password)}")
        
        # 等待登录表单加载
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)
        
        # 尝试多种选择器定位用户名输入框
        username_selectors = [
            'input#username',
            'input[name="username"]',
            'input[id*="username" i]',
            'input[name*="username" i]',
            'input[placeholder*="用户名" i]',
            'input[placeholder*="username" i]',
            'input[placeholder*="工号" i]',
            'input[type="text"]:first-of-type',
        ]
        
        username_input = None
        for selector in username_selectors:
            try:
                username_input = await page.wait_for_selector(selector, timeout=3000)
                if username_input:
                    print(f"   找到用户名输入框: {selector}")
                    break
            except:
                continue
        
        if not username_input:
            raise Exception("未找到用户名输入框")
        
        # 尝试多种选择器定位密码输入框
        password_selectors = [
            'input#password',
            'input[name="password"]',
            'input[type="password"]',
            'input[id*="password" i]',
            'input[name*="password" i]',
            'input[placeholder*="密码" i]',
            'input[placeholder*="password" i]',
        ]
        
        password_input = None
        for selector in password_selectors:
            try:
                password_input = await page.wait_for_selector(selector, timeout=3000)
                if password_input:
                    print(f"   找到密码输入框: {selector}")
                    break
            except:
                continue
        
        if not password_input:
            raise Exception("未找到密码输入框")
        
        # 清空并填写用户名
        await username_input.click()
        await username_input.fill("")
        await username_input.type(self.username, delay=50)
        
        # 清空并填写密码
        await password_input.click()
        await password_input.fill("")
        await password_input.type(self.password, delay=50)
        
        await asyncio.sleep(0.5)
        
        # 尝试多种选择器定位登录按钮
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("登录")',
            'button:has-text("Login")',
            'input[value*="登录"]',
            'input[value*="Login"]',
            'button.btn-submit',
            'button.login-btn',
            '#loginBtn',
            '.login-button',
        ]
        
        submit_button = None
        for selector in submit_selectors:
            try:
                submit_button = await page.wait_for_selector(selector, timeout=2000)
                if submit_button:
                    print(f"   找到登录按钮: {selector}")
                    break
            except:
                continue
        
        if not submit_button:
            # 如果找不到按钮，尝试按 Enter 键提交
            print("   未找到登录按钮，尝试按 Enter 键提交...")
            await password_input.press("Enter")
        else:
            await submit_button.click()
        
        print("   ⏳ 等待登录完成...")
        
        # Wait for page to settle after clicking submit before checking
        await asyncio.sleep(2)
        
        start_time = asyncio.get_event_loop().time()
        captcha_check_count = 0
        while True:
            current_time = asyncio.get_event_loop().time()
            if (current_time - start_time) > timeout_seconds:
                raise TimeoutError(f"登录超时 ({timeout_seconds} 秒)")
            
            current_url = page.url
            
            # Check if already redirected to EOMS (login succeeded, no captcha)
            if "eoms2.cmhktry.com" in current_url:
                if "/login" not in current_url.lower() and "cas" not in current_url.lower():
                    await page.wait_for_load_state("networkidle")
                    return {"success": True, "need_captcha": False}
            
            login_error = await self._detect_login_error(page)
            if login_error:
                raise Exception(f"登录失败: {login_error}")
            
            # Only check for captcha after a few loops to avoid false positives
            # during page transitions
            captcha_check_count += 1
            if captcha_check_count >= 3 and await self._is_captcha_required(page):
                print("   ⚠️ 检测到需要验证码")
                return await self._handle_captcha_flow(
                    page,
                    captcha_code=captcha_code,
                    captcha_code_provider=captcha_code_provider,
                )
            
            await asyncio.sleep(1)
    
    async def _try_trigger_sms_send(self, page: Page) -> None:
        """
        CAS 短信页通常需先点「发送验证码」才会真正发短信。
        """
        selectors = [
            "#sendSmsBtn",
            'button:has-text("发送验证码")',
            'a:has-text("发送验证码")',
            'button:has-text("獲取驗證碼")',
            'button:has-text("获取验证码")',
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    print(f"   📱 已点击发送短信/验证码: {sel}")
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                continue
    
    async def _handle_captcha_flow(
        self,
        page: Page,
        captcha_code: str = "",
        captcha_code_provider=None,
    ):
        """
        处理验证码流程（与 itsr_create.py 风格一致）：
        - 若已提供验证码则自动提交
        - 若未提供验证码则返回 need_captcha=True，由调用方二次传入
        """
        # 优先使用直接传入的验证码
        code = (captcha_code or "").strip()
        
        # 其次使用 provider 获取验证码（支持同步或异步）
        if not code and captcha_code_provider:
            try:
                maybe_code = captcha_code_provider()
                if asyncio.iscoroutine(maybe_code):
                    maybe_code = await maybe_code
                code = str(maybe_code or "").strip()
            except Exception as e:
                raise Exception(f"验证码 provider 调用失败: {e}")
        
        # 未提供验证码：先尝试触发短信发送，再交给前端输入
        if not code:
            await self._try_trigger_sms_send(page)
            await asyncio.sleep(2)
            return {
                "success": False,
                "need_captcha": True,
                "message": "检测到需要验证码，请重新调用并传入 captcha_code",
            }
        
        print("   🔢 正在提交验证码...")
        await self._submit_captcha(page, code)
        print("   ✅ 验证码提交成功，已登录")
        return {"success": True, "need_captcha": False}
    
    async def _submit_captcha(self, page: Page, code: str):
        """
        提交验证码并等待登录完成。
        支持两种常见页面：
        1) #code_input1 ~ #code_input6
        2) input[name='token'] / #sms_token
        """
        # 1) 分位输入框
        code_inputs = []
        for i in range(1, 7):
            try:
                elem = await page.query_selector(f"#code_input{i}")
                if elem and await elem.is_visible():
                    code_inputs.append(elem)
            except Exception:
                pass
        
        if len(code_inputs) >= 6 and len(code) >= 6:
            for i, ch in enumerate(code[:6]):
                await code_inputs[i].click()
                await page.keyboard.press(ch)
            # 同步隐藏字段（若存在）
            sms_token = await page.query_selector("#sms_token")
            if sms_token:
                try:
                    await sms_token.fill(code[:6])
                except Exception:
                    pass
        else:
            # 2) 单输入框 token
            token_input = None
            for selector in ['input[name="token"]', "#sms_token", 'input[name*="code" i]']:
                try:
                    elem = await page.query_selector(selector)
                    if elem and await elem.is_visible():
                        token_input = elem
                        break
                except Exception:
                    continue
            if not token_input:
                raise Exception("未找到验证码输入框")
            await token_input.click()
            await token_input.fill(code)
        
        # 提交表单
        try:
            form_submit = await page.query_selector('#fm1 input[type="submit"], #fm1 button[type="submit"]')
            if form_submit:
                await form_submit.click()
            else:
                await page.keyboard.press("Enter")
        except Exception:
            await page.keyboard.press("Enter")
        
        # 等待跳转并检查错误
        start_time = asyncio.get_event_loop().time()
        while True:
            if asyncio.get_event_loop().time() - start_time > 60:
                raise TimeoutError("验证码提交后登录超时")
            
            login_error = await self._detect_login_error(page)
            if login_error:
                raise Exception(f"验证码错误或登录失败: {login_error}")
            
            current_url = page.url
            if "eoms2.cmhktry.com" in current_url and "cas" not in current_url.lower():
                await page.wait_for_load_state("networkidle")
                return
            
            await asyncio.sleep(0.5)
    
    async def _detect_login_error(self, page: Page):
        """
        检测 CAS 页面可见登录错误（如密码错误、账号锁定等）
        只检查可见错误元素，避免扫描整页文本导致误报。
        """
        error_selectors = [
            "#msg",
            ".errors",
            ".alert-danger",
            ".error-message",
            "#login-error",
            ".login-error",
            ".cas-error",
            "#errormsg",
            ".errormsg",
            ".error",
            "#errorMessage",
        ]
        
        for selector in error_selectors:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    text = (await elem.text_content() or "").strip()
                    if text:
                        return text
            except Exception:
                continue
        
        return None
    
    async def _is_captcha_required(self, page: Page) -> bool:
        """
        检测是否出现验证码/短信验证页面。
        Only returns True when specific captcha input elements are visible,
        avoiding false positives from generic page text.
        """
        captcha_selectors = [
            "#code_input1",
            "#sms_token:not([type='hidden'])",
            "#captcha",
            "#sendSmsBtn",
            'button:has-text("发送验证码")',
        ]
        
        for selector in captcha_selectors:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    print(f"   📍 Captcha detected via selector: {selector}")
                    return True
            except Exception:
                continue
        
        # Check for split-digit code inputs (e.g. 6 individual boxes)
        visible_code_inputs = 0
        for i in range(1, 7):
            try:
                elem = await page.query_selector(f"#code_input{i}")
                if elem and await elem.is_visible():
                    visible_code_inputs += 1
            except Exception:
                pass
        if visible_code_inputs >= 4:
            print(f"   📍 Captcha detected via {visible_code_inputs} split-digit inputs")
            return True
        
        return False
    
    def _extract_def_id_from_api(self) -> str:
        """
        通过 GET 请求获取 "Service Configuration Ticket 业务配置流程" 的 defId
        
        请求 URL: https://eoms2.cmhktry.com/x5/form/dataTemplate/dataList_Top5_workflow.ht
        返回的内容包含 btn-group_1
        """
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        url = f"{self.base_url}/form/dataTemplate/dataList_Top5_workflow.ht"
        
        try:
            # 使用已捕获的 headers 和 cookies
            captured = self.home_headers if self.home_headers else self.headers
            
            headers = {
                "User-Agent": captured.get("user-agent", "Mozilla/5.0"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            # 添加其他重要 headers
            for key in ["authorization", "x-csrf-token", "x-requested-with", "referer"]:
                if key in captured:
                    headers[key] = captured[key]
            
            session = requests.Session()
            for name, value in self.cookies.items():
                session.cookies.set(name, value)
            
            print(f"📡 GET {url}")
            response = session.get(url, headers=headers, verify=False)
            
            if response.status_code != 200:
                print(f"⚠️ 请求失败，状态码: {response.status_code}")
                return ""
            
            html_content = response.text
            print(f"📄 收到响应，长度: {len(html_content)} 字符")
            
            # 从 btn-group_1 中提取 Service Configuration Ticket 的 defId
            # 格式: <a href="/x5/flow/instance/instanceToStart?defId=10000008401754">
            #       <button>Service Configuration Ticket 业务配置流程</button></a>
            
            # 方法1: 精确匹配 Service Configuration Ticket 对应的 defId
            match = re.search(
                r'defId=(\d+)[^>]*>.*?(?:Service Configuration Ticket|业务配置流程)',
                html_content,
                re.DOTALL | re.IGNORECASE
            )
            if match:
                return match.group(1)
            
            # 方法2: 匹配 btn-group_1 区域内的第一个 defId（Service Configuration 通常是第一个）
            btn_group_match = re.search(
                r'class="btn-group_1"[^>]*>(.*?)</div>',
                html_content,
                re.DOTALL | re.IGNORECASE
            )
            if btn_group_match:
                btn_group_html = btn_group_match.group(1)
                # 找第一个 defId
                first_def_id = re.search(r'defId=(\d+)', btn_group_html)
                if first_def_id:
                    return first_def_id.group(1)
            
            # 方法3: 全局搜索第一个 instanceToStart 的 defId
            all_def_ids = re.findall(r'instanceToStart\?defId=(\d+)', html_content)
            if all_def_ids:
                return all_def_ids[0]
            
            return ""
        except Exception as e:
            print(f"提取 defId 时出错: {e}")
            return ""
    
    
    def start_workflow(self, config: dict, def_id: str = None) -> dict:
        """
        启动工作流实例
        
        参数:
            config: ServiceConfig 配置字典
            def_id: 工作流定义 ID（如果不传则使用 self.def_id）
        
        返回:
            API 响应
        """
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        url = f"{self.base_url}/flow/instance/start"
        
        # 使用传入的 def_id 或已获取的 def_id
        workflow_def_id = def_id or self.def_id
        if not workflow_def_id:
            print("❌ 错误: 缺少 defId")
            return {}
        
        # 构建 Form Data（不是 JSON！）
        # 格式:
        #   defId: 10000008401754
        #   formType: inner
        #   data: {"ServiceConfig":{...}}
        form_data = {
            "defId": workflow_def_id,
            "formType": "inner",
            "data": json.dumps({"ServiceConfig": config}, ensure_ascii=False),
        }
        
        # 优先使用 /main/home 的请求头，否则使用全部捕获的请求头
        captured = self.home_headers if self.home_headers else self.headers
        
        # 构建请求头（Form Data 用 application/x-www-form-urlencoded）
        headers = {
            "User-Agent": captured.get("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        # 添加捕获的其他重要 headers
        for key in ["authorization", "x-csrf-token", "x-requested-with", "referer", "origin"]:
            if key in captured:
                headers[key] = captured[key]
        
        print(f"\n📤 正在发送请求到: {url}")
        print(f"📤 defId: {workflow_def_id}")
        print(f"📤 formType: inner")
        print(f"📤 data: {form_data['data'][:200]}...")
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        # 使用 data= 发送 Form Data（不是 json=）
        response = session.post(url, data=form_data, headers=headers, verify=False)
        
        print(f"📥 响应状态码: {response.status_code}")
        print(f"📥 响应内容: {response.text[:500]}...")
        
        return response.json() if response.text else {}
    
    def get_my_recent_instances(self, limit: int = 5) -> list:
        """
        获取当前用户最近创建的工作流实例
        
        参数:
            limit: 返回的实例数量
        
        返回:
            实例列表，每个实例包含 instId, title, createTime 等信息
        """
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Try common EOMS endpoints for listing instances
        endpoints = [
            "/flow/instance/myApply",  # 我发起的
            "/flow/instance/myList",   # 我的实例
            "/flow/task/myApply",      # 我的申请
        ]
        
        captured = self.home_headers if self.home_headers else self.headers
        headers = {
            "User-Agent": captured.get("user-agent", "Mozilla/5.0"),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json; charset=UTF-8",
        }
        for key in ["authorization", "x-csrf-token", "x-requested-with", "referer", "origin"]:
            if key in captured:
                headers[key] = captured[key]
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                # Try POST with pagination params
                payload = {
                    "pageNum": 1,
                    "pageSize": limit,
                    "orderBy": "createTime",
                    "orderType": "desc"
                }
                response = session.post(url, json=payload, headers=headers, verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("result") == 1 or data.get("success"):
                        instances = data.get("data", {}).get("list", []) or data.get("data", []) or data.get("list", [])
                        if instances:
                            print(f"✅ 从 {endpoint} 获取到 {len(instances)} 个实例")
                            return instances
            except Exception as e:
                print(f"⚠️ 尝试 {endpoint} 失败: {e}")
                continue
        
        return []
    
    def upload_file(self, file_path: str) -> dict:
        """
        上传文件到 EOMS 系统
        
        参数:
            file_path: 要上传的文件路径
        
        返回:
            包含 success, fileId, fileName, size 的字典
            例如: {"success": true, "fileId": "10000250956285", "fileName": "test.xlsx", "size": "6660"}
        """
        import requests
        import urllib3
        from pathlib import Path
        import mimetypes
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        url = f"{self.base_url}/system/file/upload"
        
        # 检查文件是否存在
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            return {"success": False, "error": "文件不存在"}
        
        # 获取文件的 MIME 类型
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            # 默认使用二进制流
            mime_type = "application/octet-stream"
        
        # 优先使用 /main/home 的请求头
        captured = self.home_headers if self.home_headers else self.headers
        
        # 构建请求头（不要设置 Content-Type，让 requests 自动处理 multipart）
        headers = {
            "User-Agent": captured.get("user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://eoms2.cmhktry.com",
            "Referer": "https://eoms2.cmhktry.com/x5/system/file/uploadDialog?max=20&type=&size=0",
        }
        # 添加捕获的其他重要 headers
        for key in ["authorization", "x-csrf-token", "x-requested-with"]:
            if key in captured:
                headers[key] = captured[key]
        
        print(f"\n📤 正在上传文件: {file_path.name}")
        print(f"📤 文件路径: {file_path}")
        print(f"📤 文件类型: {mime_type}")
        print(f"📤 上传地址: {url}")
        
        session = requests.Session()
        for name, value in self.cookies.items():
            session.cookies.set(name, value)
        
        # 使用 multipart/form-data 上传文件
        with open(file_path, "rb") as f:
            files = {
                "file": (file_path.name, f, mime_type)
            }
            response = session.post(url, files=files, headers=headers, verify=False)
        
        print(f"📥 响应状态码: {response.status_code}")
        print(f"📥 响应内容: {response.text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("success"):
                    print(f"✅ 文件上传成功! fileId: {result.get('fileId')}")
                else:
                    print(f"⚠️ 文件上传失败: {result}")
                return result
            except Exception as e:
                print(f"❌ 解析响应失败: {e}")
                return {"success": False, "error": str(e), "response": response.text}
        else:
            print(f"❌ 上传失败，状态码: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}", "response": response.text}
    
    @staticmethod
    def format_attachment(upload_results: list | dict) -> str:
        """
        将上传结果格式化为 attachment_area_updated 需要的 JSON 字符串
        
        参数:
            upload_results: 单个上传结果 dict 或多个上传结果的 list
                           格式: {"success": true, "fileId": "xxx", "fileName": "xxx", "size": "xxx"}
        
        返回:
            JSON 字符串，格式: [{"id":"xxx","name":"xxx","size":"xxx"}]
        
        示例:
            upload_result = client.upload_file("test.xlsx")
            attachment_str = client.format_attachment(upload_result)
            # 返回: '[{"id":"10000250956285","name":"test.xlsx","size":"6660"}]'
        """
        # 如果是单个结果，转换为列表
        if isinstance(upload_results, dict):
            upload_results = [upload_results]
        
        attachments = []
        for result in upload_results:
            if result.get("success") and result.get("fileId"):
                attachments.append({
                    "id": result.get("fileId"),
                    "name": result.get("fileName", ""),
                    "size": result.get("size", "0"),
                })
        
        return json.dumps(attachments, ensure_ascii=False)


def get_target_date(hours_ahead: int = 6) -> str:
    """获取目标日期时间，格式: 2025-12-08 15:57:55"""
    target = datetime.now() + timedelta(hours=hours_ahead)
    return target.strftime("%Y-%m-%d %H:%M:%S")


def build_service_config(
    # ========== 必填参数 ==========
    title: str = "",
    summary: str = "",
    originator: str = "",
    originator_group: str = "",
    originator_contacts: str = "",
    requested_to: str = "",
    requested_to_id: str = "",
    target_node: str = "",
    
    # ========== 可选参数 ==========
    workflow_category: str = "3.2.2.11 业务配置流程",
    ticket_priority: str = "Medium",
    configuration_type: str = "Internal Configuration",
    network_operation_category: str = "B",
    target_date: str = "",
    attachment_area_updated: str = "",
    description_updated: str = "",
    need_cmcc_approval: str = "No",
    
    # ========== 其他参数（默认空）==========
    **kwargs,
) -> dict:
    """
    构建 ServiceConfig
    
    必填参数:
        title: 工单标题
        summary: 工单摘要
        originator: 发起人
        originator_group: 发起人部门
        originator_contacts: 发起人邮箱
        requested_to: 处理人/团队
        requested_to_id: 处理人 ID
        target_node: 目标节点
    """
    if not target_date:
        target_date = get_target_date(6)
    
    return {
        "CMHKWorkflowCategory": workflow_category,
        "EmailAlert": "",
        "TargetNode": target_node,
        "AttachmentArea": "",
        "Fellow_Name": "",
        "SMSAlert": "",
        "Originator": originator,
        "RequestedTo": requested_to,
        "Is_Send_Boss": "0",
        "TestingPass": "",
        "initData": {},
        "Requested_To_team3_ID": "",
        "MOP_File_2_updated": "",
        "MOP_File_2": "",
        "MOP_File_3": "",
        "TargetDate": target_date,
        "Summary_updated": summary,
        "Title_updated": title,
        "OriginatorGroup": originator_group,
        "ServiceImpact": "",
        "UAT_Attachment": "",
        "Description": "",
        "Leader": "",
        "Requested_To_team2_ID": "",
        "CMCC_Approval_Attachment": "",
        "RequestedToID": requested_to_id,
        "MOP_File_1": "",
        "Need_CMCC_Approval": need_cmcc_approval,
        "Leader_Name_3": "",
        "Leader_Name_2": "",
        "Requested_To_team3": "",
        "Fellow_Name_3": "",
        "Requested_To_team2": "",
        "Fellow_Name_2": "",
        "OriginatorContacts": originator_contacts,
        "TicketPriority": ticket_priority,
        "ConfigurationType": configuration_type,
        "Comment": "",
        "Others": None,
        "Fellow_3": "",
        "Result_Log": "",
        "Fellow_2": "",
        "Configuration_Complete_Date": "",
        "Title": "",
        "MOP_File_3_updated": "",
        "Attachment_Area_Updated": attachment_area_updated,
        "Fellow": "",
        "Description_updated": description_updated,
        "NetworkOperationCategory": network_operation_category,
        "MOP_File_1_updated": "",
        "Leader_3": "",
        "Summary": "",
        "Leader_2": "",
        "Leader_Name": "",
    }


# ============================================================
# 部门配置（可选择 Cloud 或 SN）
# ============================================================
DEPARTMENTS = {
    "Cloud": {
        "requested_to": "Cloud Infrastructure",
        "requested_to_id": "10000001452280",
        "target_node": "Cloud",
    },
    "SN": {
        "requested_to": "SN & GESN",
        "requested_to_id": "10000130690460",
        "target_node": "SN",
    },
}

# ============================================================
# 默认配置（可在调用时覆盖）
# ============================================================
DEFAULT_CONFIG = {
    "originator": "",
    "originator_group": "",
    "originator_contacts": "",
    "ticket_priority": "High",
    "configuration_type": "Internal Configuration",
    "network_operation_category": "B",
    "need_cmcc_approval": "No",
    "title": "Service Configuration Request",
    "summary": "Auto-generated service configuration ticket",
}


async def create_ticket(
    target_department: str,
    username: str = "",
    password: str = "",
    title: str = None,
    summary: str = None,
    description: str = "",
    file_path: str = None,
    captcha_code: str = "",
    resume_token: str = "",
    captcha_code_provider=None,
    originator: str = None,
    originator_group: str = None,
    originator_contacts: str = None,
    ticket_priority: str = None,
    configuration_type: str = None,
    network_operation_category: str = None,
    need_cmcc_approval: str = None,
    headless: bool = True,
) -> dict:
    """
    创建 EOMS 工单（可供其他模块调用）
    
    参数:
        target_department: 目标部门，必填，可选值: "Cloud" 或 "SN"
        username: 登录用户名，必填
        password: 登录密码，必填
        title: 工单标题，可选（默认使用 DEFAULT_CONFIG）
        summary: 工单摘要，可选（默认使用 DEFAULT_CONFIG）
        description: 工单描述，可选
        file_path: 附件文件路径，可选
        originator: 发起人，可选（默认使用 DEFAULT_CONFIG）
        originator_group: 发起人部门，可选（默认使用 DEFAULT_CONFIG）
        originator_contacts: 发起人邮箱，可选（默认使用 DEFAULT_CONFIG）
        ticket_priority: 优先级，可选值: Top Urgent/High/Medium/Low
        configuration_type: 配置类型，可选
        network_operation_category: 网络操作类别，可选值: A/B/C/D
        need_cmcc_approval: 是否需要 CMCC 审批，可选值: Yes/No
        headless: 是否无头模式，默认 True
    
    返回:
        dict: 包含创建结果的字典
            - success: bool, 是否成功
            - message: str, 结果消息
            - response: dict, API 响应（如果成功）
            - error: str, 错误信息（如果失败）
    
    示例:
        # 从其他模块调用（只需传入 target_department）
        import asyncio
        from eoms_automation import create_ticket
        
        result = asyncio.run(create_ticket(target_department="SN"))
        
        # 或者自定义标题和摘要
        result = asyncio.run(create_ticket(
            target_department="SN",
            title="自定义标题",
            summary="自定义摘要",
        ))
    """
    resume_path = None
    rt = (resume_token or "").strip()
    if rt:
        if not re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            rt,
            re.I,
        ):
            return {"success": False, "error": "Invalid resume token."}
        resume_path = os.path.join(tempfile.gettempdir(), f"eoms_cas_resume_{rt}.json")
        if not os.path.isfile(resume_path):
            return {
                "success": False,
                "error": "Login session expired. Please start EOMS login again from the beginning.",
            }

    if not username or not password:
        return {"success": False, "error": "Username and password are required."}

    _title = title or DEFAULT_CONFIG["title"]
    _summary = summary or DEFAULT_CONFIG["summary"]
    _username = username
    _password = password
    _originator = originator or DEFAULT_CONFIG["originator"]
    _originator_group = originator_group or DEFAULT_CONFIG["originator_group"]
    _originator_contacts = originator_contacts or DEFAULT_CONFIG["originator_contacts"]
    _ticket_priority = ticket_priority or DEFAULT_CONFIG["ticket_priority"]
    _configuration_type = configuration_type or DEFAULT_CONFIG["configuration_type"]
    _network_operation_category = network_operation_category or DEFAULT_CONFIG["network_operation_category"]
    _need_cmcc_approval = need_cmcc_approval or DEFAULT_CONFIG["need_cmcc_approval"]
    
    print("\n" + "=" * 60)
    print("EOMS 自动化开单")
    print("=" * 60)
    
    # 1. 验证部门参数
    if target_department not in DEPARTMENTS:
        error_msg = f"无效的部门: {target_department}，可选值: {', '.join(DEPARTMENTS.keys())}"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}
    
    dept_config = DEPARTMENTS[target_department]
    print(f"📍 目标部门: {target_department}")
    print(f"   RequestedTo: {dept_config['requested_to']}")
    print(f"   TargetNode: {dept_config['target_node']}")
    print(f"📋 工单标题: {_title}")
    print(f"📋 工单摘要: {_summary}")
    if file_path:
        print(f"📎 附件: {file_path}")
    print("=" * 60)
    
    # 2. 创建客户端并登录
    client = EOmsClient(username=_username, password=_password)
    
    try:
        result = await client.login_and_capture_headers(
            headless=headless,
            timeout_seconds=30,
            captcha_code=captcha_code,
            captcha_code_provider=captcha_code_provider,
            resume_state_path=resume_path,
        )
        
        if not result:
            error_msg = "登录失败，请检查用户名和密码"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        
        if result.get("need_captcha"):
            return {
                "success": False,
                "need_captcha": True,
                "error": result.get("message", "需要验证码"),
                "resume_token": result.get("resume_token"),
            }
        
        print("✅ 登录成功")
        
    except Exception as e:
        error_msg = f"登录异常: {str(e)}"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}
    
    # 3. 上传附件（如果有）
    attachment_json = ""
    # Track fileId for use as reference
    file_id = None
    
    if file_path:
        print(f"\n📤 正在上传附件...")
        upload_result = client.upload_file(file_path)
        
        if upload_result.get("success"):
            file_id = upload_result.get("fileId")
            attachment_json = client.format_attachment(upload_result)
            print(f"✅ 附件上传成功: {attachment_json}")
        else:
            print(f"⚠️ 附件上传失败: {upload_result}")
    
    # 4. 构建工单配置
    def_id = result.get("def_id")
    if not def_id:
        error_msg = "未能获取 defId"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}
    
    config = build_service_config(
        title=_title,
        summary=_summary,
        originator=_originator,
        originator_group=_originator_group,
        originator_contacts=_originator_contacts,
        requested_to=dept_config["requested_to"],
        requested_to_id=dept_config["requested_to_id"],
        target_node=dept_config["target_node"],
        ticket_priority=_ticket_priority,
        configuration_type=_configuration_type,
        network_operation_category=_network_operation_category,
        need_cmcc_approval=_need_cmcc_approval,
        description_updated=description,
        attachment_area_updated=attachment_json,
    )
    
    # 5. 发送请求创建工单
    print(f"\n📡 正在创建工单...")
    response = client.start_workflow(config, def_id=def_id)
    
    # 6. 返回结果
    if response.get("result") == 1 or response.get("success"):
        # 提取 instId（可能在 data 里，也可能在根层级）
        inst_id = None
        data_value = response.get("data")
        
        # Case 1: data is a dict - look for instId or similar fields
        if isinstance(data_value, dict):
            inst_id = data_value.get("instId") or data_value.get("id") or data_value.get("processInstanceId") or data_value.get("ticketNo") or data_value.get("orderNo")
        # Case 2: data is a string or number that could be the instId directly
        elif data_value and isinstance(data_value, (str, int)) and str(data_value).isdigit():
            inst_id = str(data_value)
        
        # Check at root level if not found in data
        if not inst_id:
            inst_id = response.get("instId") or response.get("id") or response.get("processInstanceId") or response.get("ticketNo") or response.get("orderNo")
        
        # If no inst_id from response, use the fileId from attachment upload as reference
        if not inst_id and file_id:
            inst_id = file_id
            print(f"✅ Using fileId as ticket reference: {inst_id}")

        print(f"\n✅ 工单创建成功!")
        print(f"📋 Ticket ID: {inst_id}")
        
        # Save the ticket to database (using sync_to_async for async context)
        try:
            from asgiref.sync import sync_to_async
            from auto_tickets.models import EOMS_Tickets
            
            @sync_to_async
            def save_ticket():
                EOMS_Tickets.objects.create(
                    eoms_ticket_number=str(inst_id),
                    department=target_department,
                    requestor=_originator,
                )
            
            await save_ticket()
            print(f"💾 Ticket saved to database: {inst_id} (Department: {target_department}, Requestor: {_originator})")
        except Exception as e:
            print(f"⚠️ Failed to save ticket to database: {e}")

        if rt and resume_path and os.path.isfile(resume_path):
            try:
                os.remove(resume_path)
            except OSError:
                pass

        return {
            "success": True,
            "inst_id": inst_id,
            "message": response.get("message", "工单创建成功"),
            "response": response,
        }
    else:
        error_msg = response.get("message") or response.get("error") or "未知错误"
        print(f"\n❌ 工单创建失败: {error_msg}")
        return {
            "success": False,
            "inst_id": None,
            "error": error_msg,
            "response": response,
        }


def create_ticket_sync(
    target_department: str,
    username: str = "",
    password: str = "",
    **kwargs,
) -> dict:
    """
    创建 EOMS 工单（同步版本，方便非异步环境调用）
    参数与 create_ticket 相同，参见 create_ticket 的文档。
    """
    return asyncio.run(create_ticket(
        target_department=target_department,
        username=username,
        password=password,
        **kwargs,
    ))
