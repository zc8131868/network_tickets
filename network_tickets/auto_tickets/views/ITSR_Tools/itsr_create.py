#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITSR 工单创建主模块
==================

提供完整的工单创建（开单）流程：
    账号密码 → 登录 → 验证码 → 获取认证 → 上传附件 → 填写表单 → 提交工单

核心类：
    - CreateSession: 单个开单会话（独立线程）
    - CreateManager: 会话管理器（多线程 + 自动清理）

核心方法：
    - create_ticket_session(): 创建开单会话
    - submit_credentials(): 提交账号密码
    - submit_sms_code(): 提交验证码并执行开单
    - wait_create_result(): 等待开单结果（无需验证码时）
    - cancel_session(): 取消会话

附件说明：
    将需要上传的文件放在 attachments/ 目录下，创建时传入文件名列表。
"""

import logging
import os
import threading
import time
import uuid
import json
import mimetypes
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# 附件存放目录
ATTACHMENTS_DIR = Path(__file__).parent / "attachments"


# ============================================================================
# 数据类型定义
# ============================================================================

class SessionStatus(Enum):
    """会话状态"""
    INIT = "init"
    WAITING_CREDENTIALS = "waiting_credentials"
    LOGGING_IN = "logging_in"
    WAITING_SMS = "waiting_sms"
    CREATING = "creating"
    SUCCESS = "success"
    ERROR = "error"
    EXPIRED = "expired"
    NO_SMS_REQUIRED = "no_sms_required"


@dataclass
class CreateTicketResult:
    """开单结果"""
    success: bool = False
    case_id: str = ""
    bill_code: str = ""
    subject: str = ""
    error: str = ""


# ============================================================================
# 开单会话类
# ============================================================================

class CreateSession:
    """
    单个开单会话

    每个会话拥有独立的线程和 Playwright 实例。
    流程：创建 → 提交凭据 → (可选)提交验证码 → 上传附件 → 提交表单 → 清理
    """

    # BPM 配置
    BPM_BASE_URL = "https://bpm.cmhktry.com"

    # API 端点
    GRAPHQL_ENDPOINT = f"{BPM_BASE_URL}/service/bpm/graphql"
    SEND_ENDPOINT = f"{BPM_BASE_URL}/service/bpm/operation/send"
    FILE_UPLOAD_ENDPOINT = f"{BPM_BASE_URL}/service/itsr07195287674072066508260/file/upload"
    FILE_DETAILS_ENDPOINT = f"{BPM_BASE_URL}/service/itsr07195287674072066508260/file/details"
    USER_INFO_ENDPOINT = f"{BPM_BASE_URL}/service/itsr07195287674072066508260/i-tfuwuxuqiuxiangqing/refer-carry/organization/org-member/udcReference_FOqf_1663581049363/select-cascade-list-by-conditions"
    DEPT_INFO_ENDPOINT = f"{BPM_BASE_URL}/service/organization/graphql?organizationOrgUnitReferOrganizationOrgUnitSelectCascadeByIdsPost"
    PRODUCT_LINE_LIST_ENDPOINT = f"{BPM_BASE_URL}/service/itsr07195287674072066508260/i-tfuwuxuqiuxiangqing/page-refer/itsr07195287674072066508260/chanpinxian/2084093464378606228"
    PRODUCT_LINE_DETAIL_ENDPOINT = f"{BPM_BASE_URL}/service/itsr07195287674072066508260/i-tfuwuxuqiuxiangqing/refer-carry/itsr07195287674072066508260/chanpinxian/udcReference_iJCP_1663581049363/select-cascade-list-by-conditions"

    # 应用常量
    APP_NAME = "itsr07195287674072066508260"
    ROOT_ENTITY_NAME = "com.seeyon.itsr07195287674072066508260.domain.entity.ITfuwuxuqiu"
    PAGE_URL = "ITfuwuxuqiuxiangqing"
    PAGE_GUID = "-5702948354103621860"
    TEMPLATE_ID = "1214511312462186257"
    INSTITUTION_ID = "888802"

    def __init__(
        self,
        session_id: str,
        title: str,
        description: str,
        product_line_id: str,
        urgency: str = "DI",
        requirement_type: str = "FEIKAIFAXUQIU",
        attachment_files: Optional[List[str]] = None,
    ):
        """
        创建开单会话

        Args:
            session_id: 会话唯一标识
            title: 工单标题
            description: 需求描述
            product_line_id: 产品线 ID（可通过 list_product_lines 获取）
            urgency: 紧急程度，DI(低)/ZHONG(中)/GAO(高)，默认 DI
            requirement_type: 需求类型，FEIKAIFAXUQIU(非开发需求)/KAIFAXUQIU(开发需求)，默认 FEIKAIFAXUQIU
            attachment_files: 附件文件名列表（文件需放在 attachments/ 目录下）
        """
        self.session_id = session_id
        self.title = title
        self.description = description
        self.product_line_id = product_line_id
        self.urgency = urgency
        self.requirement_type = requirement_type
        self.attachment_files = attachment_files or []
        self.created_at = time.time()

        # 状态
        self.status = SessionStatus.WAITING_CREDENTIALS
        self.error = ""
        self.result = CreateTicketResult()

        # 认证信息（用完即删）
        self._access_token = ""
        self._uid = ""

        # Playwright 相关
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

        # 线程同步
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._credentials_event = threading.Event()
        self._sms_event = threading.Event()
        self._username = ""
        self._password = ""
        self._sms_code = ""

    # ========================================================================
    # 公共方法
    # ========================================================================

    def submit_credentials(self, username: str, password: str, timeout: int = 120) -> Tuple[bool, str]:
        """
        提交账号密码，启动登录流程

        Returns:
            (success, message)
            - success=True, message="" → 需要验证码
            - success=True, message="NO_SMS_REQUIRED" → 无需验证码，已自动开始创建
            - success=False, message=错误信息
        """
        with self._lock:
            if self.status != SessionStatus.WAITING_CREDENTIALS:
                return False, f"状态错误: {self.status.value}"
            self._username = username
            self._password = password

        self._thread = threading.Thread(target=self._login_and_create_flow, daemon=True)
        self._thread.start()
        self._credentials_event.set()

        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if self.status == SessionStatus.WAITING_SMS:
                    return True, ""
                if self.status in (SessionStatus.NO_SMS_REQUIRED, SessionStatus.CREATING, SessionStatus.SUCCESS):
                    return True, "NO_SMS_REQUIRED"
                if self.status == SessionStatus.ERROR:
                    return False, self.error
            time.sleep(0.3)

        with self._lock:
            self.status = SessionStatus.ERROR
            self.error = "登录超时"
        return False, "登录超时"

    def submit_sms_code(self, sms_code: str, timeout: int = 180) -> CreateTicketResult:
        """提交验证码，完成登录并执行开单"""
        with self._lock:
            if self.status != SessionStatus.WAITING_SMS:
                return CreateTicketResult(error=f"状态错误: {self.status.value}")
            self._sms_code = sms_code

        self._sms_event.set()

        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if self.status == SessionStatus.SUCCESS:
                    return self.result
                if self.status == SessionStatus.ERROR:
                    return CreateTicketResult(error=self.error)
            time.sleep(0.5)

        return CreateTicketResult(error="开单超时")

    def cancel(self):
        """取消会话"""
        if self.status in (SessionStatus.SUCCESS, SessionStatus.ERROR, SessionStatus.EXPIRED):
            return
        with self._lock:
            if self.status in (SessionStatus.SUCCESS, SessionStatus.ERROR, SessionStatus.EXPIRED):
                return
            self.status = SessionStatus.EXPIRED
        self._credentials_event.set()
        self._sms_event.set()
        self.cleanup()

    def is_expired(self, timeout: int = 300) -> bool:
        return time.time() - self.created_at > timeout

    def cleanup(self):
        """清理资源和认证信息"""
        self._access_token = ""
        self._uid = ""
        self._username = ""
        self._password = ""
        self._sms_code = ""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except:
            pass
        self._browser = None
        self._playwright = None
        self._page = None
        self._context = None
        logger.info(f"[{self.session_id}] 会话已清理")

    # ========================================================================
    # 私有方法 - 登录流程（复用 itsr_close.py 的逻辑）
    # ========================================================================

    def _login_and_create_flow(self):
        """登录并创建工单流程（在独立线程中运行）"""
        try:
            self._credentials_event.wait()

            with self._lock:
                if self.status == SessionStatus.EXPIRED:
                    return
                self.status = SessionStatus.LOGGING_IN

            needs_sms = self._do_playwright_login()
            if needs_sms is None:
                return

            if needs_sms:
                with self._lock:
                    self.status = SessionStatus.WAITING_SMS
                logger.info(f"[{self.session_id}] 需要验证码，等待输入...")

                if not self._sms_event.wait(timeout=300):
                    with self._lock:
                        self.status = SessionStatus.EXPIRED
                        self.error = "验证码等待超时"
                    self.cleanup()
                    return

                with self._lock:
                    if self.status == SessionStatus.EXPIRED:
                        return

                if not self._do_submit_sms():
                    return
            else:
                logger.info(f"[{self.session_id}] 无需验证码，等待认证...")
                if not self._wait_for_auth_complete():
                    return
                with self._lock:
                    self.status = SessionStatus.NO_SMS_REQUIRED
                logger.info(f"[{self.session_id}] 认证成功（无需验证码）")

            # 执行开单
            with self._lock:
                self.status = SessionStatus.CREATING
            logger.info(f"[{self.session_id}] 开始创建工单...")

            self._do_create_ticket()

        except Exception as e:
            logger.error(f"[{self.session_id}] 流程异常: {e}")
            import traceback
            traceback.print_exc()
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = str(e)
        finally:
            self.cleanup()

    def _do_playwright_login(self) -> Optional[bool]:
        """执行 Playwright 登录，返回是否需要验证码"""
        try:
            from playwright.sync_api import sync_playwright

            logger.info(f"[{self.session_id}] 启动 Playwright...")
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()

            bpm_url = "https://bpm.cmhktry.com/main/portal/ctp-affair/affairPendingCenter"

            logger.info(f"[{self.session_id}] 访问 BPM...")
            self._page.goto(bpm_url, wait_until='domcontentloaded', timeout=30000)

            logger.info(f"[{self.session_id}] 等待 CAS...")
            self._page.wait_for_url("**/ncas.hk.chinamobile.com/**", timeout=30000)

            logger.info(f"[{self.session_id}] 填写凭据: {self._username}")
            self._page.fill('input[name="username"]', self._username)
            self._page.fill('input[name="password"]', self._password)
            self._page.click('button[type="submit"], input[type="submit"]')

            logger.info(f"[{self.session_id}] 等待页面跳转...")
            self._page.wait_for_load_state('domcontentloaded', timeout=15000)

            needs_sms = self._check_if_sms_required()

            if needs_sms is None:
                # 检测到登录错误（密码错误等），状态已由 _check_if_sms_required 设置
                return None

            if needs_sms:
                logger.info(f"[{self.session_id}] 检测到需要验证码")
            else:
                logger.info(f"[{self.session_id}] 无需验证码，已直接登录")
                try:
                    self._page.wait_for_load_state('networkidle', timeout=15000)
                except:
                    self._page.wait_for_timeout(3000)

            return needs_sms

        except Exception as e:
            logger.error(f"[{self.session_id}] Playwright 登录失败: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = f"登录失败: {e}"
            self.cleanup()
            return None

    def _detect_login_error(self) -> Optional[str]:
        """
        检测 CAS 页面是否显示登录错误信息（如密码错误、账号锁定等）

        仅检查可见的错误元素，不扫描整个 page body（CAS 页面的隐藏模板/JS 中
        本身就包含 "密码错误" 等文字，扫描 body 会产生误报）。

        Returns:
            错误信息字符串（检测到错误时）
            None（未检测到错误）
        """
        try:
            # 常见 CAS 错误元素选择器（仅检测可见的）
            error_selectors = [
                '#msg',                          # CAS 通用错误消息
                '.errors',                       # CAS 错误样式
                '.alert-danger',                 # Bootstrap 错误提示
                '.error-message',                # 通用错误
                '#login-error',
                '.login-error',
                '.cas-error',
                '#errormsg',
                '.errormsg',
            ]
            for selector in error_selectors:
                elem = self._page.query_selector(selector)
                if elem and elem.is_visible():
                    text = (elem.text_content() or "").strip()
                    if text:
                        logger.warning(f"[{self.session_id}] 检测到登录错误元素 ({selector}): {text}")
                        return text

        except Exception as e:
            logger.debug(f"[{self.session_id}] 检测登录错误时异常: {e}")

        return None

    def _check_if_sms_required(self) -> Optional[bool]:
        """
        检查是否需要短信验证码

        Returns:
            True:  需要验证码
            False: 无需验证码，已直接登录
            None:  检测到登录错误（密码错误等），调用方需要处理
        """
        try:
            from urllib.parse import urlparse

            current_url = self._page.url
            logger.info(f"[{self.session_id}] 当前URL: {current_url}")

            parsed_url = urlparse(current_url)
            hostname = parsed_url.netloc

            if "bpm.cmhktry.com" in hostname:
                logger.info(f"[{self.session_id}] 已跳转到BPM，无需验证码")
                return False

            if "ncas.hk.chinamobile.com" in hostname:
                # ★ 先检测是否有登录错误（密码错误等）
                login_error = self._detect_login_error()
                if login_error:
                    logger.error(f"[{self.session_id}] 登录失败: {login_error}")
                    with self._lock:
                        self.status = SessionStatus.ERROR
                        self.error = f"登录失败: {login_error}"
                    return None

                sms_indicators = [
                    '#code_input1', '#sms_token', 'input[name="token"]',
                    '.sms-code-input', '#sendSmsBtn',
                ]
                for selector in sms_indicators:
                    elem = self._page.query_selector(selector)
                    if elem:
                        logger.info(f"[{self.session_id}] 检测到验证码元素: {selector}")
                        return True

                page_text = self._page.text_content('body') or ""
                for keyword in ['验证码', '短信验证', 'SMS', 'verification code']:
                    if keyword.lower() in page_text.lower():
                        return True

                try:
                    self._page.wait_for_function(
                        "() => window.location.hostname.includes('bpm.cmhktry.com')",
                        timeout=5000
                    )
                    return False
                except:
                    # 等了 5 秒还没跳转，再次检查错误和验证码
                    login_error = self._detect_login_error()
                    if login_error:
                        with self._lock:
                            self.status = SessionStatus.ERROR
                            self.error = f"登录失败: {login_error}"
                        return None

                    for selector in sms_indicators:
                        if self._page.query_selector(selector):
                            return True

                    # 仍无法判断，默认需要验证码
                    return True

            code_input = self._page.query_selector('#code_input1')
            if code_input:
                return True

            return False

        except Exception as e:
            logger.warning(f"[{self.session_id}] 检查验证码需求时出错: {e}")
            return True

    def _do_submit_sms(self) -> bool:
        """提交验证码并获取认证"""
        try:
            sms_code = self._sms_code
            logger.info(f"[{self.session_id}] 填写验证码: {sms_code}")

            code_inputs = []
            for i in range(1, 7):
                elem = self._page.query_selector(f'#code_input{i}')
                if elem:
                    code_inputs.append(elem)

            if len(code_inputs) == 6:
                for i, char in enumerate(sms_code):
                    code_inputs[i].click()
                    self._page.keyboard.press(char)
                self._page.wait_for_timeout(500)
                sms_token = self._page.query_selector('#sms_token')
                if sms_token:
                    sms_token.evaluate(f'el => el.value = "{sms_code}"')
            else:
                token_input = self._page.query_selector('input[name="token"]')
                if token_input:
                    token_input.fill(sms_code)

            logger.info(f"[{self.session_id}] 提交表单...")
            try:
                self._page.evaluate('document.getElementById("fm1").submit()')
            except:
                self._page.click('input[type="submit"]')

            logger.info(f"[{self.session_id}] 等待登录完成...")

            # ★ 分段等待，边等边检测错误（避免验证码错误时卡 60 秒）
            redirected = False
            for attempt in range(12):  # 最多 12 次 × 5 秒 = 60 秒
                try:
                    self._page.wait_for_url("**/bpm.cmhktry.com/**", timeout=5000)
                    redirected = True
                    break
                except:
                    # 还没跳转，检查页面是否显示错误
                    login_error = self._detect_login_error()
                    if login_error:
                        logger.error(f"[{self.session_id}] 验证码错误: {login_error}")
                        with self._lock:
                            self.status = SessionStatus.ERROR
                            self.error = f"验证码错误: {login_error}"
                        return False

                    # 检查是否还在 CAS 页面（还在说明验证码可能错误）
                    current_url = self._page.url
                    if "ncas.hk.chinamobile.com" in current_url:
                        # 检查验证码是否被清空（CAS 验证码错误时通常会清空输入框）
                        page_text = (self._page.text_content('body') or "").lower()
                        sms_error_keywords = [
                            '验证码错误', '验证码无效', '验证码已过期', '验证码不正确',
                            'invalid code', 'expired', 'incorrect',
                        ]
                        for kw in sms_error_keywords:
                            if kw.lower() in page_text:
                                logger.error(f"[{self.session_id}] 验证码错误: {kw}")
                                with self._lock:
                                    self.status = SessionStatus.ERROR
                                    self.error = f"验证码错误: {kw}"
                                return False

                    logger.debug(f"[{self.session_id}] 等待跳转... (尝试 {attempt + 1}/12)")

            if not redirected:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "验证码提交后未跳转到BPM，请检查验证码是否正确"
                return False

            try:
                with self._page.expect_response(
                    lambda r: "refresh-token" in r.url and r.status == 200,
                    timeout=30000
                ):
                    self._page.wait_for_load_state('networkidle', timeout=30000)
            except:
                self._page.wait_for_timeout(3000)

            self._extract_auth()

            if not self._access_token or not self._uid:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "未获取到认证信息"
                return False

            logger.info(f"[{self.session_id}] 获取认证成功")
            return True

        except Exception as e:
            logger.error(f"[{self.session_id}] 提交验证码失败: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = f"验证失败: {e}"
            return False

    def _extract_auth(self):
        """提取认证信息"""
        cookies = self._context.cookies()
        for cookie in cookies:
            if cookie['name'] == 'SY_ACCESS_TOKEN':
                self._access_token = cookie['value']
            elif cookie['name'] == 'SY_UID':
                self._uid = cookie['value']

        if not self._access_token or not self._uid:
            try:
                doc_cookies = self._page.evaluate('document.cookie')
                for item in doc_cookies.split(';'):
                    item = item.strip()
                    if '=' in item:
                        key, val = item.split('=', 1)
                        if key == 'SY_ACCESS_TOKEN':
                            self._access_token = val
                        elif key == 'SY_UID':
                            self._uid = val
            except:
                pass

    def _wait_for_auth_complete(self) -> bool:
        """等待认证完成（无需验证码的情况）"""
        try:
            for _ in range(30):
                self._extract_auth()
                if self._access_token and self._uid:
                    logger.info(f"[{self.session_id}] 认证获取成功: uid={self._uid}")
                    return True
                self._page.wait_for_timeout(500)

            logger.error(f"[{self.session_id}] 认证超时")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = "认证超时"
            return False

        except Exception as e:
            logger.error(f"[{self.session_id}] 认证失败: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = f"认证失败: {e}"
            return False

    # ========================================================================
    # 私有方法 - 开单流程
    # ========================================================================

    def _make_session(self) -> requests.Session:
        """创建已认证的 HTTP Session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=UTF-8',
            'Accept-Language': 'zh-TW',
            'Cookie': f'SY_ACCESS_TOKEN={self._access_token}; SY_UID={self._uid}; lang=zh-CN',
            'sy-cinfo': 'C4wfMXAR9mXTBKV1LQuL1w==',
            'Origin': self.BPM_BASE_URL,
            'Referer': f'{self.BPM_BASE_URL}/',
        })
        return session

    def _do_create_ticket(self):
        """执行创建工单的完整流程"""
        session = self._make_session()

        try:
            # 1. 获取创建页面详情（取得 permissionId 等信息）
            logger.info(f"[{self.session_id}] 步骤1: 获取创建页面详情...")
            page_detail = self._get_create_page_detail(session)
            if not page_detail:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "获取创建页面详情失败"
                return

            # 提取权限 ID
            load_page_dto = page_detail.get("loadPageDto", {})
            permission_id = load_page_dto.get("permissionId", "1038849758040920516")
            bpm_case_dto = page_detail.get("bpmCaseDto", {})
            open_time = bpm_case_dto.get("openTime", int(time.time() * 1000))

            # 2. 获取用户信息
            logger.info(f"[{self.session_id}] 步骤2: 获取用户信息...")
            user_info = self._get_user_info(session, self._uid)
            if not user_info:
                logger.warning(f"[{self.session_id}] 获取用户信息失败，使用默认值")
                user_dept_id = ""
                user_name_display = ""
                dept_name_display = ""
            else:
                user_dept_id = ""
                user_name_display = user_info.get("name", "")
                main_post = user_info.get("mainMemberPostId___displayname", {})
                if main_post:
                    user_dept_id = str(main_post.get("orgId", ""))
                    dept_name_display = main_post.get("orgName", "")
                else:
                    dept_name_display = user_info.get("orgName", "")

            # 3. 获取产品线详情
            logger.info(f"[{self.session_id}] 步骤3: 获取产品线详情...")
            product_detail = self._get_product_line_detail(session, self.product_line_id)
            if not product_detail:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "获取产品线详情失败"
                return

            cpx_bmjl = str(product_detail.get("cpxbmjl", ""))
            cpx_ywry = product_detail.get("cpxywry", "")
            banbenshenheren = str(product_detail.get("banbenshenheren", ""))
            case_sender_institution = str(product_detail.get("caseSenderInstitution", self.INSTITUTION_ID))

            # 4. 上传附件（如有）
            uploaded_files = []
            if self.attachment_files:
                logger.info(f"[{self.session_id}] 步骤4: 上传 {len(self.attachment_files)} 个附件...")
                for filename in self.attachment_files:
                    # Support absolute paths (e.g., from itsr_session_files)
                    if os.path.isabs(str(filename)):
                        file_path = Path(filename)
                    else:
                        file_path = ATTACHMENTS_DIR / filename
                    if not file_path.exists():
                        logger.warning(f"[{self.session_id}] 附件不存在: {file_path}")
                        continue
                    file_info = self._upload_file(session, file_path, user_name_display, dept_name_display)
                    if file_info:
                        uploaded_files.append(file_info)
                        logger.info(f"[{self.session_id}] 附件上传成功: {filename}")
                    else:
                        logger.warning(f"[{self.session_id}] 附件上传失败: {filename}")

            # 5. 构建附件子表数据
            attachment_dto_list = []
            for idx, finfo in enumerate(uploaded_files):
                file_size_kb = float(finfo.get("fileSize", 0)) / 1024
                file_size_str = f"{file_size_kb:.2f}KB"
                file_name = finfo.get("fileName", "")
                storage_key = finfo.get("storageKey", "")
                create_time_ms = finfo.get("createTime", int(time.time() * 1000))

                attachment_dto_list.append({
                    "shangchuanshijian": create_time_ms,
                    "shifouyibaocun": True,
                    "shangchuanrenbumen": user_dept_id,
                    "fujiandaxiao": file_size_str,
                    "shangchuanren": self._uid,
                    "fujian": storage_key,
                    "yddfjmc": f"{file_name}（{file_size_str}）",
                    "draft": False,
                    "parentId": "0",
                    "orderNo": 10000 + idx,
                    "createTime": 253402185600000,
                    "updateTime": 253402185600000,
                    "fujianmingcheng": file_name,
                    "version": 0,
                    "fujian___displayname": [finfo],
                    "shangchuanrenbumen___displayname": {
                        "validate": True,
                        "id": user_dept_id,
                        "name": dept_name_display,
                    },
                })

            # ================================================================
            # 6. 第一次 send — 创建草稿（获取 caseId, formRecordId）
            # ================================================================
            logger.info(f"[{self.session_id}] 步骤5: 创建草稿...")
            draft_result = self._send_create_draft(
                session=session,
                permission_id=permission_id,
                open_time=open_time,
                case_sender_institution=case_sender_institution,
                user_dept_id=user_dept_id,
                cpx_bmjl=cpx_bmjl,
                cpx_ywry=cpx_ywry,
                banbenshenheren=banbenshenheren,
                attachment_dto_list=attachment_dto_list,
            )

            if not draft_result:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "创建草稿失败"
                return

            if draft_result.get("status") != 0:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = draft_result.get("message", "创建草稿失败")
                return

            draft_content = draft_result.get("data", {}).get("content", {})
            case_id = str(draft_content.get("caseId", ""))
            subject = draft_content.get("subject", "")
            form_record_id = str(draft_content.get("formRecorderId", draft_content.get("formRecordId", "")))
            draft_form_data = draft_content.get("formData", {})
            bill_code = draft_form_data.get("billCode", "")

            logger.info(f"[{self.session_id}] 草稿已创建: caseId={case_id}, formRecordId={form_record_id}, billCode={bill_code}")

            # ================================================================
            # 7. 获取草稿详情（取得 affairId, opinionId, openTime）
            # ================================================================
            logger.info(f"[{self.session_id}] 步骤6: 获取草稿详情...")
            draft_detail = self._get_draft_detail(session, case_id, form_record_id, permission_id)

            if not draft_detail:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "获取草稿详情失败"
                return

            bpm_case_dto = draft_detail.get("bpmCaseDto", {})
            affair_id = ""
            opinion_id = ""

            # 从 nodePermission 的 operationList 中提取 affairId 不在这里
            # affairId 来自 workflowItemId 或需要从 affair 列表中获取
            # 实际上 affairId 在 bpmCaseDto 的关联中不直接给出，需要从 opinion 里找
            # 根据 HAR: affairId 在 opinion 查询中获取，或在详情的 workflowItemId

            # 尝试获取 affairId
            # 方法1: 从 bpmShareInfoDto 获取
            share_info = draft_detail.get("bpmShareInfoDto", {})
            if share_info:
                affair_id = str(share_info.get("affairId", ""))

            # 方法2: 从 detail 的顶级字段获取
            if not affair_id:
                affair_id = str(draft_detail.get("affairId", ""))

            # 方法3: 通过查询 affair 列表获取
            if not affair_id:
                affair_id = self._get_affair_id_for_case(session, case_id)

            if not affair_id:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "获取 affairId 失败"
                return

            # 获取 opinionId（从详情中的 opinion 列表提取）
            opinion_id = self._get_opinion_id(session, case_id, affair_id)

            draft_open_time = bpm_case_dto.get("openTime", open_time)

            logger.info(f"[{self.session_id}] affairId={affair_id}, opinionId={opinion_id}")

            # ================================================================
            # 8. 第二次 send — 真正提交（newSend=true，获取条件匹配）
            # ================================================================
            logger.info(f"[{self.session_id}] 步骤7: 提交工单（newSend）...")
            request_id = f"COLLOABORATION_{int(time.time() * 1000)}"

            submit_result = self._send_submit_draft(
                session=session,
                case_id=case_id,
                affair_id=affair_id,
                form_record_id=form_record_id,
                open_time=draft_open_time,
                opinion_id=opinion_id,
                request_id=request_id,
            )

            if not submit_result:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "提交工单失败"
                return

            if submit_result.get("status") != 0:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = submit_result.get("message", "提交工单失败")
                return

            submit_content = submit_result.get("data", {}).get("content", {})
            pre_match = submit_content.get("preMatchResponseDto")

            if pre_match and pre_match.get("conditionMatchResultDtoMap"):
                condition_map = pre_match["conditionMatchResultDtoMap"]

                # conditionsOfLinks 的值是 branchMatchResult 的反转:
                # AUTO_TRUE (匹配) → false, AUTO_FALSE (不匹配) → true
                conditions_of_links = {}
                for key, val in condition_map.items():
                    conditions_of_links[key] = not val.get("branchMatchResult", False)

                # ============================================================
                # 9. 第三次 send — 确认条件路由
                # ============================================================
                logger.info(f"[{self.session_id}] 步骤8: 确认条件路由...")
                confirm_result = self._send_confirm_conditions(
                    session=session,
                    case_id=case_id,
                    affair_id=affair_id,
                    form_record_id=form_record_id,
                    open_time=draft_open_time,
                    opinion_id=opinion_id,
                    request_id=request_id,
                    conditions_of_links=conditions_of_links,
                )

                if not confirm_result:
                    with self._lock:
                        self.status = SessionStatus.ERROR
                        self.error = "确认条件路由失败"
                    return

                if confirm_result.get("status") != 0:
                    with self._lock:
                        self.status = SessionStatus.ERROR
                        self.error = confirm_result.get("message", "确认条件路由失败")
                    return

                final_content = confirm_result.get("data", {}).get("content", {})
                final_form_data = final_content.get("formData", {})
                bill_code = final_form_data.get("billCode", bill_code)
                subject = final_content.get("subject", subject)

            # 成功
            with self._lock:
                self.result = CreateTicketResult(
                    success=True,
                    case_id=case_id,
                    bill_code=bill_code,
                    subject=subject,
                )
                self.status = SessionStatus.SUCCESS

            logger.info(f"[{self.session_id}] 工单创建成功: caseId={case_id}, billCode={bill_code}, subject={subject}")

        except Exception as e:
            logger.error(f"[{self.session_id}] 创建工单异常: {e}")
            import traceback
            traceback.print_exc()
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = str(e)

    def _get_create_page_detail(self, session: requests.Session) -> Optional[Dict]:
        """获取创建页面详情（GraphQL）"""
        payload = {
            "query": """mutation graphqlLoader ($params0: bpmSummarySelectDetailPostInputBody) { 
  data0: bpmSummarySelectDetailPost(body: $params0) { code data { content } message status } }""",
            "variables": {
                "params0": {
                    "pageGuid": self.PAGE_GUID,
                    "appName": self.APP_NAME,
                    "rootEntityName": self.ROOT_ENTITY_NAME,
                    "pageUrl": self.PAGE_URL,
                    "pageType": "PC",
                    "systemSettingCodes": [
                        "COMMENTS_INPUT_BOX_SETTING",
                        "ACTIVITY_INFORM_OPERATE",
                        "AFFAIR_CONSULT_OPINION",
                        "ACTIVITY_ADD_OPERATE",
                        "BPM_OPINION"
                    ]
                }
            }
        }

        try:
            resp = session.post(
                f"{self.GRAPHQL_ENDPOINT}?bpmSummarySelectDetailPost",
                json=payload, timeout=30
            )
            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] GraphQL HTTP错误: {resp.status_code}")
                return None

            data = resp.json()
            data0 = data.get("data", {}).get("data0", {})
            if data0.get("status") != 0:
                logger.error(f"[{self.session_id}] GraphQL 查询失败: {data0.get('message')}")
                return None

            return data0.get("data", {}).get("content", {})

        except Exception as e:
            logger.error(f"[{self.session_id}] 获取页面详情异常: {e}")
            return None

    def _get_user_info(self, session: requests.Session, uid: str) -> Optional[Dict]:
        """获取用户信息（姓名、部门等）"""
        try:
            resp = session.post(
                self.USER_INFO_ENDPOINT,
                json={"ids": [uid]},
                timeout=30
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            content = data.get("data", {}).get("content", [])
            if content:
                return content[0]
            return None

        except Exception as e:
            logger.error(f"[{self.session_id}] 获取用户信息异常: {e}")
            return None

    def _get_product_line_detail(self, session: requests.Session, product_line_id: str) -> Optional[Dict]:
        """获取产品线详情"""
        try:
            resp = session.post(
                self.PRODUCT_LINE_DETAIL_ENDPOINT,
                json={"ids": [product_line_id]},
                timeout=30
            )
            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] 产品线详情 HTTP错误: {resp.status_code}")
                return None

            data = resp.json()
            content = data.get("data", {}).get("content", [])
            if content:
                return content[0]
            return None

        except Exception as e:
            logger.error(f"[{self.session_id}] 获取产品线详情异常: {e}")
            return None

    def _upload_file(self, session: requests.Session, file_path: Path, user_name: str, dept_name: str) -> Optional[Dict]:
        """上传单个文件，返回文件详情 dict"""
        try:
            mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

            # 构建 multipart 表单
            # 注意：上传时不设置全局 Content-Type（让 requests 自动处理 boundary）
            upload_headers = dict(session.headers)
            upload_headers.pop('Content-Type', None)

            user_name_json = json.dumps({"en": user_name, "zh_CN": user_name}, ensure_ascii=False)
            dept_name_json = json.dumps({"en": dept_name, "zh_CN": dept_name}, ensure_ascii=False)

            with open(file_path, 'rb') as f:
                files = {
                    'file': (file_path.name, f, mime_type),
                }
                form_data = {
                    'isPublic': 'false',
                    'metadata': '',
                    'createUserName': user_name_json,
                    'createDeptName': dept_name_json,
                }

                # 使用 session.post 保留认证 cookies；临时去除 Content-Type 让 requests 自动处理 boundary
                saved_ct = session.headers.pop('Content-Type', None)
                resp = session.post(
                    self.FILE_UPLOAD_ENDPOINT,
                    files=files,
                    data=form_data,
                    timeout=60
                )
                if saved_ct:
                    session.headers['Content-Type'] = saved_ct

            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] 文件上传 HTTP错误: {resp.status_code}")
                return None

            data = resp.json()
            if data.get("status") != 0:
                logger.error(f"[{self.session_id}] 文件上传失败: {data.get('message')}")
                return None

            content = data.get("data", {}).get("content", {})
            # content 可能是 list 或 dict
            if isinstance(content, list):
                file_info = content[0] if content else {}
            else:
                file_info = content
            storage_key = file_info.get("storageKey", "")

            if not storage_key:
                logger.error(f"[{self.session_id}] 上传成功但无 storageKey")
                return None

            # 获取文件详情
            detail_resp = session.post(
                self.FILE_DETAILS_ENDPOINT,
                json={"storageKeys": [storage_key]},
                timeout=30
            )
            if detail_resp.status_code == 200:
                detail_data = detail_resp.json()
                details = detail_data.get("data", {}).get("content", [])
                if details:
                    return details[0]

            # 回退使用上传返回的信息
            return file_info

        except Exception as e:
            logger.error(f"[{self.session_id}] 文件上传异常: {e}")
            return None

    # ========================================================================
    # 步骤6: 创建草稿
    # ========================================================================

    def _send_create_draft(
        self,
        session: requests.Session,
        permission_id: str,
        open_time: int,
        case_sender_institution: str,
        user_dept_id: str,
        cpx_bmjl: str,
        cpx_ywry: str,
        banbenshenheren: str,
        attachment_dto_list: List[Dict],
    ) -> Optional[Dict]:
        """第一次 send: 创建草稿，获得 caseId / formRecordId"""
        faqirenyijibumen = "1151247876479782877"  # 信息技术中心

        form_data = {
            "__key": "14159265356",
            "templateId": "0",
            "caseId": "0",
            "caseSender": self._uid,
            "caseSenderInstitution": case_sender_institution,
            "chulisudupingfen": "FIVE",
            "chulizhiliangpingfen": "FIVE",
            "fwtdpf": "FIVE",
            "sfxgcpx": False,
            "sfxgxqlx": True,
            "shifoukaishijiedian": True,
            "faqirenyijibumen": faqirenyijibumen,
            "qcrszdbm": user_dept_id,
            "banbenshenheren": banbenshenheren,
            "clmxdqxcs": "",
            "mxbcshz": "",
            "mxbcpxbmjlhz": "",
            "mxbxmjlhz": "",
            "cpxbmjl": cpx_bmjl,
            "cpxywry": cpx_ywry,
            "statusType": "DRAFT",
            "yewujieduan": "XUQIUTICHU",
            "shifoudaiban": "1",
            "yinzangfujian": "",
            "faqryzfj": "",
            "kfcsyzfj": "",
            "xmjlsxzd": "",
            "xuqiutichufujian": "",
            "famxhclmxdqxID": "0",
            "csylfjmb": "",
            "zhengdanfujianmingxiDtoList": attachment_dto_list,
            "biaoti": self.title,
            "xuqiumiaoshu": self.description,
            "chanpinxiandanxuansingle": self.product_line_id,
            "jinjichengdu": self.urgency,
            "xuqiuleixing": self.requirement_type,
        }

        payload = {
            "isSendAction": False,
            "hostAppName": "",
            "rootEntityName": self.ROOT_ENTITY_NAME,
            "applicationName": self.APP_NAME,
            "formData": form_data,
            "formRecordId": "",
            "templateId": self.TEMPLATE_ID,
            "preMatchRequestDto": {"oneHandlerMatchNeedPop": False},
            "caseId": "",
            "changeNodeRequestDtos": [],
            "bpmOpinionDto": {
                "id": None,
                "objectId": "10",
                "subObjectId": "1000",
                "content": self.title,
                "richContent": "",
                "attachmentStorageIds": [],
                "opinion": "",
                "showPerson": f"{self._uid},{self._uid}",
                "extra": {"hidden": False, "opinionHidden": f"{self._uid},{self._uid}"},
                "userIds": [],
                "createUserName": "",
                "operationCaption": '{"zh_CN":"提交"}'
            },
            "openTime": open_time,
            "evaluationRecordDtoList": [],
            "commentRequired": True,
            "trackRequestDto": {
                "isTrack": True, "trackType": "ALL",
                "affairId": None, "caseId": None, "processId": "", "trackValues": []
            },
            "informAddSelectPeoples": "[]",
            "requestId": "",
            "newSend": False,
            "importance": "NORMAL"
        }

        try:
            resp = session.post(self.SEND_ENDPOINT, json=payload, timeout=60)
            logger.info(f"[{self.session_id}] 创建草稿响应: HTTP {resp.status_code}")
            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] HTTP错误: {resp.status_code}, {resp.text[:500]}")
                return None
            return resp.json()
        except Exception as e:
            logger.error(f"[{self.session_id}] 创建草稿异常: {e}")
            return None

    # ========================================================================
    # 步骤7: 获取草稿详情 + affairId
    # ========================================================================

    def _get_draft_detail(self, session: requests.Session, case_id: str, form_record_id: str, permission_id: str) -> Optional[Dict]:
        """获取草稿的详情（带 affairId, permissionId 等）"""
        # 先通过 share 接口获取 affairId
        share_payload = {
            "query": """mutation graphqlLoader ($params0: bpmSummarySharePostInputBody) {
  data0: bpmSummarySharePost(body: $params0) { code data { content } message status } }""",
            "variables": {
                "params0": {
                    "caseId": case_id,
                    "detailType": "SHARE"
                }
            }
        }

        try:
            resp = session.post(
                f"{self.GRAPHQL_ENDPOINT}?bpmSummarySharePost",
                json=share_payload, timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                share_content = data.get("data", {}).get("data0", {}).get("data", {}).get("content", {})
                affair_id = str(share_content.get("affairId", ""))
                if affair_id:
                    logger.info(f"[{self.session_id}] 从 share 接口获取 affairId={affair_id}")
                    # 保存到实例
                    self._draft_affair_id = affair_id
        except Exception as e:
            logger.warning(f"[{self.session_id}] share 接口异常: {e}")

        # 获取完整详情
        affair_id = getattr(self, '_draft_affair_id', '')
        detail_payload = {
            "query": """mutation graphqlLoader ($params0: bpmSummarySelectDetailPostInputBody) { 
  data0: bpmSummarySelectDetailPost(body: $params0) { code data { content } message status } }""",
            "variables": {
                "params0": {
                    "affairId": affair_id,
                    "caseId": case_id,
                    "detailType": "SHARE",
                    "permissionId": permission_id,
                    "templateId": self.TEMPLATE_ID,
                    "pageGuid": self.PAGE_GUID,
                    "appName": self.APP_NAME,
                    "rootEntityName": self.ROOT_ENTITY_NAME,
                    "pageUrl": self.PAGE_URL,
                    "pageType": "PC",
                    "systemSettingCodes": [
                        "COMMENTS_INPUT_BOX_SETTING", "ACTIVITY_INFORM_OPERATE",
                        "AFFAIR_CONSULT_OPINION", "ACTIVITY_ADD_OPERATE", "BPM_OPINION"
                    ]
                }
            }
        }

        try:
            resp = session.post(
                f"{self.GRAPHQL_ENDPOINT}?bpmSummarySelectDetailPost",
                json=detail_payload, timeout=30
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            data0 = data.get("data", {}).get("data0", {})
            if data0.get("status") != 0:
                logger.error(f"[{self.session_id}] 草稿详情查询失败: {data0.get('message')}")
                return None
            return data0.get("data", {}).get("content", {})
        except Exception as e:
            logger.error(f"[{self.session_id}] 获取草稿详情异常: {e}")
            return None

    def _get_affair_id_for_case(self, session: requests.Session, case_id: str) -> str:
        """通过 share 接口获取 affairId"""
        return getattr(self, '_draft_affair_id', '')

    def _get_opinion_id(self, session: requests.Session, case_id: str, affair_id: str) -> str:
        """获取 opinionId（从意见列表中提取）"""
        payload = {
            "query": """mutation graphqlLoader ($params0: bpmSummarySelectOpinionByDimensionPostInputBody) {
  data0: bpmSummarySelectOpinionByDimensionPost(body: $params0) { code data { content } message status } }""",
            "variables": {
                "params0": {
                    "affairId": affair_id,
                    "caseId": case_id,
                    "dimensionType": "NODE"
                }
            }
        }

        try:
            resp = session.post(
                f"{self.GRAPHQL_ENDPOINT}?bpmSummarySelectOpinionByDimensionPost",
                json=payload, timeout=30
            )
            if resp.status_code != 200:
                return ""

            data = resp.json()
            content = data.get("data", {}).get("data0", {}).get("data", {}).get("content", {})

            # content 通常是按节点分组的意见列表
            # 遍历找到当前用户的意见 ID
            if isinstance(content, dict):
                for node_key, opinions in content.items():
                    if isinstance(opinions, list):
                        for op in opinions:
                            op_id = op.get("id", "")
                            if op_id:
                                logger.info(f"[{self.session_id}] 获取 opinionId={op_id}")
                                return str(op_id)
            elif isinstance(content, list):
                for op in content:
                    op_id = op.get("id", "")
                    if op_id:
                        return str(op_id)

            return ""
        except Exception as e:
            logger.warning(f"[{self.session_id}] 获取 opinionId 异常: {e}")
            return ""

    # ========================================================================
    # 步骤8: 真正提交（newSend=true）
    # ========================================================================

    def _send_submit_draft(
        self,
        session: requests.Session,
        case_id: str,
        affair_id: str,
        form_record_id: str,
        open_time: int,
        opinion_id: str,
        request_id: str,
    ) -> Optional[Dict]:
        """第二次 send: newSend=true，从草稿状态真正提交，获取条件匹配"""
        payload = {
            "isSendAction": False,
            "hostAppName": "",
            "rootEntityName": self.ROOT_ENTITY_NAME,
            "applicationName": self.APP_NAME,
            "formData": {
                "id": form_record_id,
            },
            "formRecordId": form_record_id,
            "templateId": self.TEMPLATE_ID,
            "preMatchRequestDto": {"oneHandlerMatchNeedPop": False},
            "caseId": case_id,
            "affairId": affair_id,
            "changeNodeRequestDtos": [],
            "bpmOpinionDto": {
                "id": opinion_id or None,
                "objectId": case_id,
                "subObjectId": affair_id,
                "content": self.title,
                "richContent": "",
                "attachmentStorageIds": [],
                "opinion": "",
                "showPerson": f"{self._uid},{self._uid}",
                "extra": {
                    "associateDocument": [],
                    "hidden": False,
                    "opinionHidden": f"{self._uid},{self._uid}"
                },
                "operationCaption": '{"zh_CN":"提交"}'
            },
            "openTime": open_time,
            "evaluationRecordDtoList": [],
            "commentRequired": True,
            "trackRequestDto": {
                "isTrack": True, "trackType": "ALL",
                "affairId": affair_id, "caseId": case_id,
                "processId": "", "trackValues": []
            },
            "informAddSelectPeoples": "[]",
            "requestId": request_id,
            "newSend": True,
            "subject": self.title,
            "importance": "NONE"
        }

        try:
            resp = session.post(self.SEND_ENDPOINT, json=payload, timeout=60)
            logger.info(f"[{self.session_id}] 提交草稿响应: HTTP {resp.status_code}")
            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] HTTP错误: {resp.status_code}, {resp.text[:500]}")
                return None
            return resp.json()
        except Exception as e:
            logger.error(f"[{self.session_id}] 提交草稿异常: {e}")
            return None

    # ========================================================================
    # 步骤9: 确认条件路由
    # ========================================================================

    def _send_confirm_conditions(
        self,
        session: requests.Session,
        case_id: str,
        affair_id: str,
        form_record_id: str,
        open_time: int,
        opinion_id: str,
        request_id: str,
        conditions_of_links: Dict[str, bool],
    ) -> Optional[Dict]:
        """第三次 send: 确认条件路由，工单正式发出"""
        payload = {
            "isSendAction": False,
            "hostAppName": "",
            "rootEntityName": self.ROOT_ENTITY_NAME,
            "applicationName": self.APP_NAME,
            "formData": {"id": form_record_id},
            "formRecordId": form_record_id,
            "templateId": self.TEMPLATE_ID,
            "preMatchRequestDto": {
                "conditionsOfLinks": conditions_of_links,
                "selectedPeoplesOfNodes": {},
                "nodeSubLicenseMap": {},
                "oneHandlerMatchNeedPop": False,
            },
            "caseId": case_id,
            "affairId": affair_id,
            "changeNodeRequestDtos": [],
            "bpmOpinionDto": {
                "id": opinion_id or None,
                "objectId": case_id,
                "subObjectId": affair_id,
                "content": self.title,
                "richContent": "",
                "attachmentStorageIds": [],
                "opinion": "",
                "showPerson": f"{self._uid},{self._uid}",
                "extra": {
                    "associateDocument": [],
                    "hidden": False,
                    "opinionHidden": f"{self._uid},{self._uid}"
                },
                "operationCaption": '{"zh_CN":"提交"}'
            },
            "openTime": open_time,
            "evaluationRecordDtoList": [],
            "commentRequired": True,
            "trackRequestDto": {
                "isTrack": True, "trackType": "ALL",
                "affairId": affair_id, "caseId": case_id,
                "processId": "", "trackValues": []
            },
            "informAddSelectPeoples": "[]",
            "requestId": request_id,
            "newSend": False,
            "subject": self.title,
            "importance": "NONE"
        }

        try:
            resp = session.post(self.SEND_ENDPOINT, json=payload, timeout=60)
            logger.info(f"[{self.session_id}] 确认条件响应: HTTP {resp.status_code}")
            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] HTTP错误: {resp.status_code}, {resp.text[:500]}")
                return None
            return resp.json()
        except Exception as e:
            logger.error(f"[{self.session_id}] 确认条件异常: {e}")
            return None


# ============================================================================
# 会话管理器
# ============================================================================

class CreateManager:
    """
    开单会话管理器

    - 管理多个并发的开单会话
    - 自动清理过期会话（默认5分钟）
    - 线程安全
    """

    def __init__(self, session_timeout: int = 300):
        self.session_timeout = session_timeout
        self._sessions: Dict[str, CreateSession] = {}
        self._lock = threading.Lock()

        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("CreateManager 已启动")

    def create_session(
        self,
        title: str,
        description: str,
        product_line_id: str,
        urgency: str = "DI",
        requirement_type: str = "FEIKAIFAXUQIU",
        attachment_files: Optional[List[str]] = None,
    ) -> str:
        session_id = str(uuid.uuid4())[:8]
        sess = CreateSession(
            session_id=session_id,
            title=title,
            description=description,
            product_line_id=product_line_id,
            urgency=urgency,
            requirement_type=requirement_type,
            attachment_files=attachment_files,
        )
        with self._lock:
            self._sessions[session_id] = sess
        logger.info(f"创建开单会话: {session_id}, 标题: {title}")
        return session_id

    def get_session(self, session_id: str) -> Optional[CreateSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def remove_session(self, session_id: str):
        with self._lock:
            sess = self._sessions.pop(session_id, None)
        if sess:
            if sess.status not in (SessionStatus.SUCCESS, SessionStatus.ERROR, SessionStatus.EXPIRED):
                sess.cancel()
            logger.info(f"移除会话: {session_id}")

    def _cleanup_loop(self):
        while True:
            time.sleep(30)
            expired = []
            with self._lock:
                for sid, sess in self._sessions.items():
                    if sess.is_expired(self.session_timeout):
                        expired.append(sid)
            for sid in expired:
                self.remove_session(sid)
                logger.info(f"自动清理过期会话: {sid}")


# ============================================================================
# 全局管理器
# ============================================================================

_manager: Optional[CreateManager] = None


def get_manager() -> CreateManager:
    global _manager
    if _manager is None:
        _manager = CreateManager()
    return _manager


# ============================================================================
# 辅助函数（无需登录）
# ============================================================================

def list_product_lines(access_token: str, uid: str) -> List[Dict]:
    """
    获取可用产品线列表（需要已有的认证信息）

    Args:
        access_token: JWT Token
        uid: 用户 ID

    Returns:
        产品线列表，每项包含 id, archiveCaption(名称), cpxjssm(说明)
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
        'Content-Type': 'application/json;charset=UTF-8',
        'Cookie': f'SY_ACCESS_TOKEN={access_token}; SY_UID={uid}; lang=zh-CN',
        'sy-cinfo': 'C4wfMXAR9mXTBKV1LQuL1w==',
    })

    payload = {
        "pageInfo": {"needTotal": True, "pageNumber": 1, "pageSize": 50},
        "referGuid": "2084093464378606228",
        "searchParams": {
            "logicalOperator": "AND",
            "searchParam": {},
            "expressionValues": {},
            "one2OneEntityRelationsV2": [],
            "sortSettings": None
        }
    }

    resp = session.post(
        f"https://bpm.cmhktry.com/service/itsr07195287674072066508260/i-tfuwuxuqiuxiangqing/page-refer/itsr07195287674072066508260/chanpinxian/2084093464378606228",
        json=payload,
        timeout=30
    )

    if resp.status_code != 200:
        return []

    data = resp.json()
    content = data.get("data", {}).get("content", [])
    return [
        {
            "id": item.get("id"),
            "name": item.get("archiveCaption"),
            "description": item.get("cpxjssm", ""),
        }
        for item in content
    ]


# ============================================================================
# 主要 API 函数
# ============================================================================

def create_ticket_session(
    title: str,
    description: str,
    product_line_id: str,
    urgency: str = "GAO",
    requirement_type: str = "FEIKAIFAXUQIU",
    attachment_files: Optional[List[str]] = None,
) -> str:
    """
    创建开单会话

    Args:
        title: 工单标题
        description: 需求描述
        product_line_id: 产品线 ID（可通过 list_product_lines 获取）
        urgency: 紧急程度 DI(低)/ZHONG(中)/GAO(高)，默认 DI
        requirement_type: 需求类型 FEIKAIFAXUQIU(非开发需求)/KAIFAXUQIU(开发需求)，默认 FEIKAIFAXUQIU
        attachment_files: 附件文件名列表（文件放在 attachments/ 目录下）

    Returns:
        session_id: 会话 ID

    Example:
        session_id = create_ticket_session(
            title="测试工单",
            description="这是一个测试",
            product_line_id="1254515022491552748",
            urgency="DI",
            attachment_files=["test.xlsx"]
        )
    """
    return get_manager().create_session(
        title=title,
        description=description,
        product_line_id=product_line_id,
        urgency=urgency,
        requirement_type=requirement_type,
        attachment_files=attachment_files,
    )


def submit_credentials(session_id: str, username: str, password: str) -> Tuple[bool, str]:
    """
    提交账号密码（自动判断是否需要验证码）

    Args:
        session_id: 会话 ID
        username: 用户名
        password: 密码

    Returns:
        (success, message)
        - success=True, message="" → 需要验证码
        - success=True, message="NO_SMS_REQUIRED" → 无需验证码，正在创建
        - success=False, message=错误信息

    Example:
        success, msg = submit_credentials(session_id, "PY0121", "password")
        if success and msg == "NO_SMS_REQUIRED":
            result = wait_create_result(session_id)
        elif success:
            result = submit_sms_code(session_id, "123456")
        else:
            print(f"登录失败: {msg}")
    """
    sess = get_manager().get_session(session_id)
    if not sess:
        return False, "会话不存在或已过期"
    return sess.submit_credentials(username, password)


def submit_sms_code(session_id: str, sms_code: str) -> CreateTicketResult:
    """
    提交验证码并执行开单

    Args:
        session_id: 会话 ID
        sms_code: 6位短信验证码

    Returns:
        CreateTicketResult:
            success, case_id, bill_code, subject, error

    Example:
        result = submit_sms_code(session_id, "123456")
        if result.success:
            print(f"工单创建成功: {result.bill_code}")
    """
    sess = get_manager().get_session(session_id)
    if not sess:
        return CreateTicketResult(error="会话不存在或已过期")

    result = sess.submit_sms_code(sms_code)
    get_manager().remove_session(session_id)
    return result


def wait_create_result(session_id: str, timeout: int = 180) -> CreateTicketResult:
    """
    等待开单结果（无需验证码时调用）

    Args:
        session_id: 会话 ID
        timeout: 超时秒数

    Returns:
        CreateTicketResult
    """
    sess = get_manager().get_session(session_id)
    if not sess:
        return CreateTicketResult(error="会话不存在或已过期")

    start_time = time.time()
    while time.time() - start_time < timeout:
        with sess._lock:
            if sess.status == SessionStatus.SUCCESS:
                result = sess.result
                get_manager().remove_session(session_id)
                return result
            if sess.status == SessionStatus.ERROR:
                result = CreateTicketResult(error=sess.error)
                get_manager().remove_session(session_id)
                return result
            if sess.status == SessionStatus.EXPIRED:
                get_manager().remove_session(session_id)
                return CreateTicketResult(error="会话已过期")
        time.sleep(0.3)

    return CreateTicketResult(error="开单超时")


def cancel_session(session_id: str):
    """取消会话"""
    get_manager().remove_session(session_id)


def get_session_status(session_id: str) -> Optional[str]:
    """获取会话状态"""
    sess = get_manager().get_session(session_id)
    if sess:
        return sess.status.value
    return None


# ============================================================================
# 交互式开单函数（命令行测试用）
# ============================================================================

def create_ticket_interactive(
    title: str,
    description: str,
    product_line_id: str,
    urgency: str = "DI",
    requirement_type: str = "FEIKAIFAXUQIU",
    attachment_files: Optional[List[str]] = None,
) -> CreateTicketResult:
    """
    交互式开单（命令行测试用）

    自动判断是否需要验证码。

    Args:
        title: 工单标题
        description: 需求描述
        product_line_id: 产品线 ID
        urgency: 紧急程度
        requirement_type: 需求类型
        attachment_files: 附件文件名列表
    """
    print(f"\n准备创建工单:")
    print(f"  标题: {title}")
    print(f"  描述: {description[:50]}{'...' if len(description) > 50 else ''}")
    print(f"  产品线ID: {product_line_id}")
    print(f"  紧急程度: {urgency}")
    print(f"  需求类型: {requirement_type}")
    if attachment_files:
        print(f"  附件: {', '.join(attachment_files)}")

    session_id = create_ticket_session(
        title=title,
        description=description,
        product_line_id=product_line_id,
        urgency=urgency,
        requirement_type=requirement_type,
        attachment_files=attachment_files,
    )
    print(f"  会话ID: {session_id}")

    username = input("\n用户名: ").strip()
    password = input("密码: ").strip()

    print("正在登录...")
    success, msg = submit_credentials(session_id, username, password)

    if not success:
        print(f"登录失败: {msg}")
        return CreateTicketResult(error=msg)

    if msg == "NO_SMS_REQUIRED":
        print("无需验证码，正在创建工单...")
        result = wait_create_result(session_id)
    else:
        print("登录成功，需要验证码...")
        sms_code = input("验证码 (6位): ").strip()
        print("正在创建工单...")
        result = submit_sms_code(session_id, sms_code)

    if result.success:
        print(f"\n工单创建成功!")
        print(f"  工单号: {result.bill_code}")
        print(f"  Case ID: {result.case_id}")
        print(f"  标题: {result.subject}")
    else:
        print(f"\n工单创建失败: {result.error}")

    return result


# ============================================================================
# 命令行入口
# ============================================================================

if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    parser = argparse.ArgumentParser(
        description='ITSR 工单创建工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创建工单（交互式输入账号密码）
  python itsr_create.py --title "测试工单" --desc "描述" --product-line "1254515022491552748"

  # 创建工单并上传附件（文件放在 attachments/ 目录下）
  python itsr_create.py --title "测试" --desc "描述" --product-line "1254515022491552748" --files test.xlsx

  # 列出产品线（需要先有 token）
  python itsr_create.py --list-products --token "eyJ..." --uid "305..."

产品线 ID 常用值:
  ISM (網絡支撐):                    1254515022491552748
  ISM (辦公設備、TRY...):             1314344591033369789
  ISM (數據庫、服務器...):             1314344591033402557
  BOSS-Market (个人及家宽):           1254544470548940586
  BOSS-Corporate (CHBN):            1254544470548973354
  BOSS系統運營支撐維護:               1254541485026577388
  MSS (協同辦公...):                  1254547142958124012

紧急程度: DI(低) / ZHONG(中) / GAO(高)
需求类型: FEIKAIFAXUQIU(非开发需求) / KAIFAXUQIU(开发需求)
        """
    )

    parser.add_argument('--title', help='工单标题')
    parser.add_argument('--desc', help='需求描述')
    parser.add_argument('--product-line', help='产品线 ID')
    parser.add_argument('--urgency', default='DI', choices=['DI', 'ZHONG', 'GAO'], help='紧急程度（默认 DI）')
    parser.add_argument('--req-type', default='FEIKAIFAXUQIU', choices=['FEIKAIFAXUQIU', 'KAIFAXUQIU'], help='需求类型')
    parser.add_argument('--files', nargs='*', help='附件文件名（放在 attachments/ 目录下）')
    parser.add_argument('--list-products', action='store_true', help='列出可用产品线')
    parser.add_argument('--token', help='JWT Token（仅 --list-products 使用）')
    parser.add_argument('--uid', help='用户 ID（仅 --list-products 使用）')
    parser.add_argument('--debug', action='store_true', help='开启调试日志')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_products:
        if not args.token or not args.uid:
            print("--list-products 需要 --token 和 --uid 参数")
            exit(1)
        products = list_product_lines(args.token, args.uid)
        print(f"\n产品线列表（共 {len(products)} 个）:\n")
        for p in products:
            print(f"  ID: {p['id']}")
            print(f"  名称: {p['name']}")
            if p.get('description'):
                print(f"  说明: {p['description'][:80]}")
            print()
        exit(0)

    if args.title and args.desc and args.product_line:
        create_ticket_interactive(
            title=args.title,
            description=args.desc,
            product_line_id=args.product_line,
            urgency=args.urgency,
            requirement_type=args.req_type,
            attachment_files=args.files,
        )
    else:
        parser.print_help()
