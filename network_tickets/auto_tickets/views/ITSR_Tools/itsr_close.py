#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITSR 工单关闭主模块
==================

提供完整的工单关闭流程：
    工单号 → 登录 → 验证码 → 获取认证 → 关单 → 清除缓存

核心类：
    - CloseSession: 单个关单会话（独立线程）
    - CloseManager: 会话管理器（多线程 + 自动清理）

核心方法：
    - create_close_session(): 创建关单会话
    - submit_credentials(): 提交账号密码
    - submit_sms_code(): 提交验证码并执行关单
    - cancel_session(): 取消会话
"""

import logging
import threading
import time
import uuid
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# 数据库管理器（可选）
_db_manager = None

def get_db_manager():
    """获取数据库管理器（延迟加载）"""
    global _db_manager
    if _db_manager is None:
        try:
            from db_manager import DBManager
            _db_manager = DBManager()
            if _db_manager.test_connection():
                logger.info("数据库连接成功")
            else:
                logger.warning("数据库连接失败，将不会回写数据库")
                _db_manager = None
        except Exception as e:
            logger.warning(f"无法加载数据库模块: {e}")
            _db_manager = None
    return _db_manager


# ============================================================================
# 数据类型定义
# ============================================================================

class SessionStatus(Enum):
    """会话状态"""
    INIT = "init"                    # 初始化
    WAITING_CREDENTIALS = "waiting_credentials"  # 等待账号密码
    LOGGING_IN = "logging_in"        # 登录中
    WAITING_SMS = "waiting_sms"      # 等待验证码
    CLOSING = "closing"              # 关单中
    SUCCESS = "success"              # 成功
    ERROR = "error"                  # 失败
    EXPIRED = "expired"              # 过期


@dataclass
class TicketCloseResult:
    """单个工单关闭结果"""
    ticket_number: str
    success: bool
    message: str


@dataclass
class CloseSessionResult:
    """关单会话结果"""
    success: bool = False
    results: List[TicketCloseResult] = field(default_factory=list)
    error: str = ""
    
    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)
    
    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if not r.success)


# ============================================================================
# 关单会话类
# ============================================================================

class CloseSession:
    """
    单个关单会话
    
    每个会话拥有独立的线程和 Playwright 实例。
    流程：创建 → 提交凭据 → 提交验证码 → 关单 → 清理
    """
    
    # 工单关闭 API 配置
    DETAIL_ENDPOINT = "https://bpm.cmhktry.com/service/serverQuery/data/dataQuery"
    SUBMIT_ENDPOINT = "https://bpm.cmhktry.com/service/serverQuery/submit"
    PRECHECK_ENDPOINT = "https://bpm.cmhktry.com/service/bpm/bizBpm/preCheck"
    APP_NAME = "ITSR"
    ROOT_ENTITY_NAME = "ITSR"
    PAGE_URL = "/main/itsr/itsr-Alldetail"
    PAGE_GUID = "8a64c07e88698302018945e0a5ed0d41"
    
    def __init__(self, session_id: str, ticket_numbers: List[str], update_db: bool = True):
        """
        创建关单会话
        
        Args:
            session_id: 会话唯一标识
            ticket_numbers: 要关闭的工单号列表
            update_db: 关单成功后是否更新数据库（默认True）
        """
        self.session_id = session_id
        self.ticket_numbers = ticket_numbers
        self.update_db = update_db
        self.created_at = time.time()
        
        # 状态
        self.status = SessionStatus.WAITING_CREDENTIALS
        self.error = ""
        self.results: List[TicketCloseResult] = []
        
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
    
    def submit_credentials(self, username: str, password: str, timeout: int = 60) -> Tuple[bool, str]:
        """
        提交账号密码，启动登录流程
        
        Args:
            username: 用户名
            password: 密码
            timeout: 等待超时（秒）
        
        Returns:
            (success, error_message)
        """
        with self._lock:
            if self.status != SessionStatus.WAITING_CREDENTIALS:
                return False, f"状态错误: {self.status.value}"
            self._username = username
            self._password = password
        
        # 启动登录线程
        self._thread = threading.Thread(target=self._login_and_close_flow, daemon=True)
        self._thread.start()
        
        # 通知线程开始
        self._credentials_event.set()
        
        # 等待到达验证码页面
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if self.status == SessionStatus.WAITING_SMS:
                    return True, ""
                if self.status == SessionStatus.ERROR:
                    return False, self.error
            time.sleep(0.5)
        
        with self._lock:
            self.status = SessionStatus.ERROR
            self.error = "登录超时"
        return False, "登录超时"
    
    def submit_sms_code(self, sms_code: str, timeout: int = 180) -> CloseSessionResult:
        """
        提交验证码，完成登录并执行关单
        
        Args:
            sms_code: 6位短信验证码
            timeout: 等待超时（秒）
        
        Returns:
            CloseSessionResult
        """
        with self._lock:
            if self.status != SessionStatus.WAITING_SMS:
                return CloseSessionResult(error=f"状态错误: {self.status.value}")
            self._sms_code = sms_code
        
        # 通知线程继续
        self._sms_event.set()
        
        # 等待完成
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if self.status == SessionStatus.SUCCESS:
                    return CloseSessionResult(success=True, results=self.results)
                if self.status == SessionStatus.ERROR:
                    return CloseSessionResult(error=self.error, results=self.results)
            time.sleep(0.5)
        
        return CloseSessionResult(error="关单超时")
    
    def cancel(self):
        """取消会话"""
        with self._lock:
            self.status = SessionStatus.EXPIRED
        self._credentials_event.set()
        self._sms_event.set()
        self.cleanup()
    
    def is_expired(self, timeout: int = 300) -> bool:
        """检查是否过期"""
        return time.time() - self.created_at > timeout
    
    def cleanup(self):
        """清理资源和认证信息"""
        # 清除认证信息
        self._access_token = ""
        self._uid = ""
        self._username = ""
        self._password = ""
        self._sms_code = ""
        
        # 清理 Playwright
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
    # 私有方法
    # ========================================================================
    
    def _login_and_close_flow(self):
        """登录并关单流程（在独立线程中运行）"""
        try:
            # 等待凭据
            self._credentials_event.wait()
            
            with self._lock:
                if self.status == SessionStatus.EXPIRED:
                    return
                self.status = SessionStatus.LOGGING_IN
            
            # 执行 Playwright 登录
            if not self._do_playwright_login():
                return
            
            # 等待验证码
            with self._lock:
                self.status = SessionStatus.WAITING_SMS
            logger.info(f"[{self.session_id}] 等待验证码...")
            
            # 等待验证码（5分钟超时）
            if not self._sms_event.wait(timeout=300):
                with self._lock:
                    self.status = SessionStatus.EXPIRED
                    self.error = "验证码等待超时"
                self.cleanup()
                return
            
            with self._lock:
                if self.status == SessionStatus.EXPIRED:
                    return
            
            # 提交验证码并获取认证
            if not self._do_submit_sms():
                return
            
            # 执行关单
            with self._lock:
                self.status = SessionStatus.CLOSING
            logger.info(f"[{self.session_id}] 开始关闭 {len(self.ticket_numbers)} 个工单...")
            
            self._do_close_tickets()
            
            with self._lock:
                self.status = SessionStatus.SUCCESS
            logger.info(f"[{self.session_id}] ✅ 关单完成")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] 流程异常: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = str(e)
        
        finally:
            self.cleanup()
    
    def _do_playwright_login(self) -> bool:
        """执行 Playwright 登录（到验证码页面）"""
        try:
            from playwright.sync_api import sync_playwright
            
            logger.info(f"[{self.session_id}] 启动 Playwright...")
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            
            bpm_url = "https://bpm.cmhktry.com/main/portal/ctp-affair/affairPendingCenter?portletTitle=%E5%BE%85%E8%BE%A6%E4%BA%8B%E9%A0%85"
            
            logger.info(f"[{self.session_id}] 访问 BPM...")
            self._page.goto(bpm_url, wait_until='domcontentloaded', timeout=30000)
            
            logger.info(f"[{self.session_id}] 等待 CAS...")
            self._page.wait_for_url("**/ncas.hk.chinamobile.com/**", timeout=30000)
            
            logger.info(f"[{self.session_id}] 填写凭据: {self._username}")
            self._page.fill('input[name="username"]', self._username)
            self._page.fill('input[name="password"]', self._password)
            self._page.click('button[type="submit"], input[type="submit"]')
            
            logger.info(f"[{self.session_id}] 等待验证码页面...")
            self._page.wait_for_load_state('domcontentloaded', timeout=10000)
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Playwright 登录失败: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = f"登录失败: {e}"
            self.cleanup()
            return False
    
    def _do_submit_sms(self) -> bool:
        """提交验证码并获取认证"""
        try:
            sms_code = self._sms_code
            logger.info(f"[{self.session_id}] 填写验证码: {sms_code}")
            
            # 6个独立输入框
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
            
            # 提交
            logger.info(f"[{self.session_id}] 提交表单...")
            try:
                self._page.evaluate('document.getElementById("fm1").submit()')
            except:
                self._page.click('input[type="submit"]')
            
            # 等待跳转
            logger.info(f"[{self.session_id}] 等待登录完成...")
            self._page.wait_for_url("**/bpm.cmhktry.com/**", timeout=60000)
            
            # 等待 refresh-token
            try:
                with self._page.expect_response(
                    lambda r: "refresh-token" in r.url and r.status == 200,
                    timeout=30000
                ):
                    self._page.wait_for_load_state('networkidle', timeout=30000)
            except:
                self._page.wait_for_timeout(3000)
            
            # 提取认证
            self._extract_auth()
            
            if not self._access_token or not self._uid:
                with self._lock:
                    self.status = SessionStatus.ERROR
                    self.error = "未获取到认证信息"
                return False
            
            logger.info(f"[{self.session_id}] ✅ 获取认证成功")
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
    
    def _do_close_tickets(self):
        """执行关单"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=UTF-8',
            'Cookie': f'SY_ACCESS_TOKEN={self._access_token}; SY_UID={self._uid}',
            'sy-cinfo': f'{{"sId":"","pInfo":[],"uId":"{self._uid}","cId":"","cNo":"","tId":""}}'
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        for ticket_num in self.ticket_numbers:
            result = self._close_single_ticket(session, ticket_num)
            self.results.append(result)
            
            if result.success:
                logger.info(f"[{self.session_id}] ✅ {ticket_num} 关闭成功")
                
                # 回写数据库
                if self.update_db:
                    self._update_db_status(ticket_num)
            else:
                logger.error(f"[{self.session_id}] ❌ {ticket_num} 关闭失败: {result.message}")
    
    def _update_db_status(self, ticket_number: str):
        """更新数据库中的 itsr_status 为 closed"""
        try:
            db = get_db_manager()
            if db:
                success = db.mark_itsr_closed(ticket_number)
                if success:
                    logger.info(f"[{self.session_id}] 📝 数据库已更新: {ticket_number} -> closed")
                else:
                    logger.warning(f"[{self.session_id}] 数据库更新失败: {ticket_number}")
        except Exception as e:
            logger.warning(f"[{self.session_id}] 数据库更新异常: {e}")
    
    def _close_single_ticket(self, session: requests.Session, ticket_number: str) -> TicketCloseResult:
        """关闭单个工单"""
        try:
            # 获取详情
            detail = self._get_ticket_detail(session, ticket_number)
            if not detail:
                return TicketCloseResult(ticket_number, False, "获取工单详情失败")
            
            # 获取子表
            zibiao = self._get_zibiao(session, detail['id'])
            
            # 执行关单
            success, msg = self._do_close(session, detail, zibiao)
            return TicketCloseResult(ticket_number, success, msg)
            
        except Exception as e:
            return TicketCloseResult(ticket_number, False, str(e))
    
    def _get_ticket_detail(self, session: requests.Session, ticket_number: str) -> Optional[Dict]:
        """获取工单详情"""
        payload = {
            "appName": self.APP_NAME,
            "pageGuid": self.PAGE_GUID,
            "rootEntityName": self.ROOT_ENTITY_NAME,
            "rootWhere": f"number='{ticket_number}'",
            "dataEntityName": self.ROOT_ENTITY_NAME,
            "isContainRootEntity": True,
            "isCustom": True,
            "pageSize": 20,
            "pageNum": 1,
            "lang": "zh-CN"
        }
        
        resp = session.post(self.DETAIL_ENDPOINT, json=payload, timeout=30)
        data = resp.json()
        
        if data.get('status') == 0 and data.get('data', {}).get('list'):
            return data['data']['list'][0]
        return None
    
    def _get_zibiao(self, session: requests.Session, ticket_id: str) -> List[Dict]:
        """获取子表数据"""
        payload = {
            "appName": self.APP_NAME,
            "pageGuid": self.PAGE_GUID,
            "rootEntityName": self.ROOT_ENTITY_NAME,
            "rootWhere": f"id='{ticket_id}'",
            "dataEntityName": "ITSRzibiao",
            "isCustom": True,
            "pageSize": 100,
            "pageNum": 1,
            "lang": "zh-CN"
        }
        
        resp = session.post(self.DETAIL_ENDPOINT, json=payload, timeout=30)
        data = resp.json()
        
        if data.get('status') == 0:
            return data.get('data', {}).get('list', [])
        return []
    
    def _do_close(self, session: requests.Session, detail: Dict, zibiao: List[Dict]) -> Tuple[bool, str]:
        """执行关单"""
        form_data = {
            "id": detail['id'],
            "number": detail['number'],
            "status": "close",
            "closeStatus": "normal",
            "solution": "已解决",
            "solutionDetails": "已解决",
            "answer": "已处理",
            "ITSRzibiao": zibiao
        }
        
        # PreCheck
        precheck_payload = {
            "appName": self.APP_NAME,
            "pageGuid": self.PAGE_GUID,
            "eventSourceGuid": "",
            "nodeGuid": "",
            "microFlowGuid": "",
            "dataObject": {"ITSR": form_data},
            "rootName": self.ROOT_ENTITY_NAME,
            "url": self.PAGE_URL
        }
        
        resp = session.post(self.PRECHECK_ENDPOINT, json=precheck_payload, timeout=30)
        precheck = resp.json()
        
        if precheck.get('status') != 0:
            return False, f"PreCheck失败: {precheck.get('message')}"
        
        precheck_data = precheck.get('data', {})
        
        # Submit
        submit_payload = {
            "appName": self.APP_NAME,
            "pageGuid": self.PAGE_GUID,
            "submitButtonGuid": "8a64c07e886983020189466af9460def",
            "preMatchRequestDto": {
                "conditionsOfLinks": precheck_data.get('conditionsOfLinks', {}),
                "flowObjList": precheck_data.get('flowObjList', []),
                "dataObj": {"ITSR": form_data}
            },
            "formData": {"ITSR": form_data},
            "url": self.PAGE_URL,
            "opinion": "同意",
            "rootName": self.ROOT_ENTITY_NAME
        }
        
        resp = session.post(self.SUBMIT_ENDPOINT, json=submit_payload, timeout=30)
        result = resp.json()
        
        if result.get('status') == 0:
            return True, "关闭成功"
        return False, result.get('message', '未知错误')


# ============================================================================
# 会话管理器
# ============================================================================

class CloseManager:
    """
    关单会话管理器
    
    - 管理多个并发的关单会话
    - 自动清理过期会话（默认5分钟）
    - 线程安全
    """
    
    def __init__(self, session_timeout: int = 300):
        """
        Args:
            session_timeout: 会话超时时间（秒），默认5分钟
        """
        self.session_timeout = session_timeout
        self._sessions: Dict[str, CloseSession] = {}
        self._lock = threading.Lock()
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("CloseManager 已启动，自动清理线程运行中")
    
    def create_session(self, ticket_numbers: List[str], update_db: bool = True) -> str:
        """
        创建关单会话
        
        Args:
            ticket_numbers: 要关闭的工单号列表
            update_db: 关单成功后是否更新数据库（默认True）
        
        Returns:
            session_id: 会话唯一标识
        """
        session_id = str(uuid.uuid4())[:8]
        session = CloseSession(session_id, ticket_numbers, update_db)
        
        with self._lock:
            self._sessions[session_id] = session
        
        logger.info(f"创建会话: {session_id}, 工单数: {len(ticket_numbers)}, 回写DB: {update_db}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[CloseSession]:
        """获取会话"""
        with self._lock:
            return self._sessions.get(session_id)
    
    def remove_session(self, session_id: str):
        """移除会话"""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        
        if session:
            session.cancel()
            logger.info(f"移除会话: {session_id}")
    
    def _cleanup_loop(self):
        """定期清理过期会话"""
        while True:
            time.sleep(30)
            
            expired = []
            with self._lock:
                for sid, session in self._sessions.items():
                    if session.is_expired(self.session_timeout):
                        expired.append(sid)
            
            for sid in expired:
                self.remove_session(sid)
                logger.info(f"自动清理过期会话: {sid}")


# ============================================================================
# 全局管理器
# ============================================================================

_manager: Optional[CloseManager] = None


def get_manager() -> CloseManager:
    """获取全局管理器"""
    global _manager
    if _manager is None:
        _manager = CloseManager()
    return _manager


# ============================================================================
# 主要 API 函数
# ============================================================================

def create_close_session(ticket_numbers: List[str], update_db: bool = True) -> str:
    """
    创建关单会话
    
    Args:
        ticket_numbers: 要关闭的工单号列表，如 ["ITSR001", "ITSR002"]
        update_db: 关单成功后是否更新数据库 itsr_status='closed'（默认True）
    
    Returns:
        session_id: 会话ID，用于后续操作
    
    Example:
        session_id = create_close_session(["ITSR001", "ITSR002"])
        session_id = create_close_session(["ITSR001"], update_db=False)  # 不更新数据库
    """
    return get_manager().create_session(ticket_numbers, update_db)


def submit_credentials(session_id: str, username: str, password: str) -> Tuple[bool, str]:
    """
    提交账号密码，启动登录流程
    
    Args:
        session_id: 会话ID
        username: 用户名
        password: 密码
    
    Returns:
        (success, error_message)
        - success=True 表示已到达验证码页面，等待输入验证码
        - success=False 表示登录失败，error_message 包含错误信息
    
    Example:
        success, error = submit_credentials(session_id, "PY0121", "password")
        if success:
            print("请输入验证码")
        else:
            print(f"登录失败: {error}")
    """
    session = get_manager().get_session(session_id)
    if not session:
        return False, "会话不存在或已过期"
    
    return session.submit_credentials(username, password)


def submit_sms_code(session_id: str, sms_code: str) -> CloseSessionResult:
    """
    提交验证码，完成登录并执行关单
    
    Args:
        session_id: 会话ID
        sms_code: 6位短信验证码
    
    Returns:
        CloseSessionResult:
            - success: 是否成功
            - results: 每个工单的关闭结果列表
            - error: 错误信息
            - success_count: 成功数量
            - fail_count: 失败数量
    
    Example:
        result = submit_sms_code(session_id, "123456")
        if result.success:
            print(f"成功: {result.success_count}, 失败: {result.fail_count}")
            for r in result.results:
                print(f"  {r.ticket_number}: {r.message}")
        else:
            print(f"失败: {result.error}")
    """
    session = get_manager().get_session(session_id)
    if not session:
        return CloseSessionResult(error="会话不存在或已过期")
    
    result = session.submit_sms_code(sms_code)
    
    # 完成后移除会话
    get_manager().remove_session(session_id)
    
    return result


def cancel_session(session_id: str):
    """
    取消会话
    
    Args:
        session_id: 会话ID
    
    Example:
        cancel_session(session_id)
    """
    get_manager().remove_session(session_id)


def get_session_status(session_id: str) -> Optional[str]:
    """
    获取会话状态
    
    Args:
        session_id: 会话ID
    
    Returns:
        状态字符串，如 "waiting_credentials", "waiting_sms", "closing" 等
        如果会话不存在返回 None
    
    Example:
        status = get_session_status(session_id)
        print(f"当前状态: {status}")
    """
    session = get_manager().get_session(session_id)
    if session:
        return session.status.value
    return None


# ============================================================================
# 一站式关单函数（用于测试）
# ============================================================================

def close_tickets_interactive(ticket_numbers: List[str], update_db: bool = True) -> CloseSessionResult:
    """
    交互式关单（命令行测试用）
    
    Args:
        ticket_numbers: 工单号列表
        update_db: 关单成功后是否更新数据库（默认True）
    
    Returns:
        CloseSessionResult
    """
    print(f"\n准备关闭 {len(ticket_numbers)} 个工单: {', '.join(ticket_numbers)}")
    print(f"数据库回写: {'开启' if update_db else '关闭'}")
    
    # 创建会话
    session_id = create_close_session(ticket_numbers, update_db)
    print(f"会话ID: {session_id}")
    
    # 输入凭据
    username = input("用户名: ").strip()
    password = input("密码: ").strip()
    
    success, error = submit_credentials(session_id, username, password)
    if not success:
        print(f"❌ 登录失败: {error}")
        return CloseSessionResult(error=error)
    
    print("✅ 登录成功，等待验证码...")
    
    # 输入验证码
    sms_code = input("验证码 (6位): ").strip()
    
    print("正在关闭工单...")
    result = submit_sms_code(session_id, sms_code)
    
    if result.success:
        print(f"\n✅ 关单完成！成功: {result.success_count}, 失败: {result.fail_count}")
        for r in result.results:
            status = "✅" if r.success else "❌"
            print(f"  {status} {r.ticket_number}: {r.message}")
    else:
        print(f"\n❌ 关单失败: {result.error}")
    
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
    
    parser = argparse.ArgumentParser(description='ITSR 工单关闭工具')
    parser.add_argument('tickets', nargs='*', help='工单号列表')
    parser.add_argument('--no-db', action='store_true', help='不更新数据库')
    
    args = parser.parse_args()
    
    if args.tickets:
        tickets = args.tickets
    else:
        print("ITSR 工单关闭工具")
        print("用法: python itsr_close.py ITSR001 ITSR002 ...")
        print("      python itsr_close.py --no-db ITSR001  # 不更新数据库")
        tickets_input = input("\n请输入工单号（空格分隔）: ").strip()
        tickets = tickets_input.split()
    
    if tickets:
        close_tickets_interactive(tickets, update_db=not args.no_db)
    else:
        print("未输入工单号")

