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
import re
import threading
import time
import uuid
import requests
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# BPM may redirect to legacy HK CAS or cmhktry CAS (same IdP family as EOMS Playwright flow)
_CAS_LOGIN_URL_RE = re.compile(
    r".*(ncas\.hk\.chinamobile\.com|ncas\.cmhktry\.com).*",
    re.I,
)


def _bpm_is_unauthenticated_login_url(url: str) -> bool:
    """bpm.cmhktry.com/login is NOT an SSO success page (no SY_* cookies)."""
    try:
        p = urlparse(url)
        if 'bpm.cmhktry.com' not in (p.netloc or ''):
            return False
        path = (p.path or '/').rstrip('/') or '/'
        return path == '/login' or path.startswith('/login/')
    except Exception:
        return False


def _try_bpm_sso_from_login_page(page, session_id: str) -> bool:
    """
    Many BPM deployments show /login after CAS with a link to CAS/SSO; without a click,
    SY_ACCESS_TOKEN is never set. Returns True if a control was clicked.
    """
    if not _bpm_is_unauthenticated_login_url(page.url):
        return False
    href_selectors = (
        'a[href*="ncas"]',
        'a[href*="cas/login"]',
        'a[href*="/cas/"]',
        'a[href*="sso"]',
        'a[href*="SSO"]',
    )
    for sel in href_selectors:
        try:
            loc = page.locator(sel)
            if loc.count() == 0:
                continue
            el = loc.first
            el.wait_for(state='visible', timeout=4000)
            logger.info(f"[{session_id}] BPM /login: 点击链接 {sel!r}")
            el.click(timeout=20000)
            try:
                page.wait_for_load_state('domcontentloaded', timeout=60000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            return True
        except Exception as e:
            logger.debug(f"[{session_id}] BPM /login {sel}: {e}")

    for hint in (
        '单点登录', '统一认证', '统一登陆', '域登录', '域账号',
        '企业登录', '企业用户', 'CAS', 'SSO',
    ):
        try:
            pat = re.compile(re.escape(hint), re.I)
            for role in ('link', 'button'):
                loc = page.get_by_role(role, name=pat)
                if loc.count() == 0:
                    continue
                el = loc.first
                el.wait_for(state='visible', timeout=2500)
                logger.info(f"[{session_id}] BPM /login: 点击 {role} {hint!r}")
                el.click(timeout=20000)
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=60000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


# ============================================================================
# Django cache integration (for multi-worker deployments)
# ============================================================================
#
# IMPORTANT:
# - We do NOT store thread/lock/playwright objects in cache (not serializable).
# - We store only session state (status/results/error) and coordination flags
#   (sms_code/cancelled) so that different web workers can participate in the
#   multi-step flow.
#
# Lazy import: Django cache may not be available at module import time
_django_cache = None
_HAS_DJANGO_CACHE = None  # None = not checked yet, True/False = checked

_CACHE_PREFIX_STATE = "itsr_close:state:"
_CACHE_PREFIX_SMS = "itsr_close:sms:"
_CACHE_PREFIX_CANCEL = "itsr_close:cancel:"
_CACHE_PREFIX_STARTED = "itsr_close:started:"

# Keep cache entries long enough for multi-step human interaction.
# (The CloseManager legacy in-memory cleanup used 300s; cache TTL is separate.)
_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


def _cache_key(prefix: str, session_id: str) -> str:
    return f"{prefix}{session_id}"


def _cache_enabled() -> bool:
    """Lazy check: try to import Django cache if not already done."""
    global _django_cache, _HAS_DJANGO_CACHE
    
    # If already checked, return cached result
    if _HAS_DJANGO_CACHE is not None:
        return bool(_HAS_DJANGO_CACHE and _django_cache is not None)
    
    # Try to import Django cache (may fail if Django not initialized)
    try:
        from django.core.cache import cache as _django_cache  # type: ignore
        _HAS_DJANGO_CACHE = True
        return True
    except Exception as e:
        logger.debug(f"Cache not available: {e}")
        _django_cache = None
        _HAS_DJANGO_CACHE = False
        return False


def _state_to_result_list(results: List[Dict]) -> List["TicketCloseResult"]:
    out: List[TicketCloseResult] = []
    for r in results or []:
        try:
            out.append(
                TicketCloseResult(
                    ticket_number=str(r.get("ticket_number", "")),
                    success=bool(r.get("success", False)),
                    message=str(r.get("message", "")),
                )
            )
        except Exception:
            continue
    return out


def _results_to_state_list(results: List["TicketCloseResult"]) -> List[Dict]:
    return [
        {"ticket_number": r.ticket_number, "success": bool(r.success), "message": r.message}
        for r in (results or [])
    ]


def _cache_get_state(session_id: str) -> Optional[Dict]:
    if not _cache_enabled():
        return None
    try:
        return _django_cache.get(_cache_key(_CACHE_PREFIX_STATE, session_id))
    except Exception as e:
        logger.warning(f"[{session_id}] 读取缓存状态失败: {e}")
        return None


def _cache_set_state(session_id: str, state: Dict, ttl: int = _CACHE_TTL_SECONDS):
    if not _cache_enabled():
        return
    try:
        _django_cache.set(_cache_key(_CACHE_PREFIX_STATE, session_id), state, timeout=ttl)
    except Exception as e:
        logger.warning(f"[{session_id}] 写入缓存状态失败: {e}")


def _cache_update_state(session_id: str, **updates):
    """
    Update cached state dict with fields in updates.
    """
    state = _cache_get_state(session_id) or {}
    state.update(updates)
    # Always refresh a heartbeat timestamp and TTL.
    state["updated_at"] = time.time()
    _cache_set_state(session_id, state)


def _cache_set_sms_code(session_id: str, sms_code: str):
    if not _cache_enabled():
        return
    try:
        _django_cache.set(_cache_key(_CACHE_PREFIX_SMS, session_id), str(sms_code), timeout=_CACHE_TTL_SECONDS)
    except Exception as e:
        logger.warning(f"[{session_id}] 写入验证码缓存失败: {e}")


def _cache_get_sms_code(session_id: str) -> str:
    if not _cache_enabled():
        return ""
    try:
        val = _django_cache.get(_cache_key(_CACHE_PREFIX_SMS, session_id))
        return str(val).strip() if val else ""
    except Exception:
        return ""


def _cache_set_cancelled(session_id: str):
    if not _cache_enabled():
        return
    try:
        _django_cache.set(_cache_key(_CACHE_PREFIX_CANCEL, session_id), True, timeout=_CACHE_TTL_SECONDS)
    except Exception as e:
        logger.warning(f"[{session_id}] 写入取消标记失败: {e}")


def _cache_is_cancelled(session_id: str) -> bool:
    if not _cache_enabled():
        return False
    try:
        return bool(_django_cache.get(_cache_key(_CACHE_PREFIX_CANCEL, session_id)))
    except Exception:
        return False


def _cache_try_mark_started(session_id: str) -> bool:
    """
    Returns True only for the first caller that starts processing this session.
    Uses cache.add() for a best-effort cross-worker lock.
    """
    if not _cache_enabled():
        return True
    try:
        # cache.add returns False if key already exists
        return bool(_django_cache.add(_cache_key(_CACHE_PREFIX_STARTED, session_id), True, timeout=_CACHE_TTL_SECONDS))
    except Exception:
        # If cache backend doesn't support add reliably, fall back to allowing start.
        return True

# 数据库管理器（可选）
_db_manager = None

def get_db_manager():
    """获取数据库管理器（延迟加载）"""
    global _db_manager
    if _db_manager is None:
        try:
            from auto_tickets.views.ITSR_Tools.db_manager import DBManager
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
    NO_SMS_REQUIRED = "no_sms_required"  # 无需验证码，直接登录成功


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
    
    # 工单关闭 API 配置 (使用 BPM 原生 API)
    BPM_BASE_URL = "https://bpm.cmhktry.com"
    # 事项列表 API - 根据工单编号搜索获取 caseId/affairId 等信息
    LIST_ENDPOINT = f"{BPM_BASE_URL}/service/itsr07195287674072066508260/i-tfuwuxuqiuliebiao-user/filter-plan/itsr07195287674072066508260/shixiang/1164050706911494756"
    # GraphQL API - 获取工单详情和子表数据
    GRAPHQL_ENDPOINT = f"{BPM_BASE_URL}/service/bpm/graphql"
    # 关单提交 API
    SUBMIT_ENDPOINT = f"{BPM_BASE_URL}/service/bpm/operation/submit"

    # 待办入口（CAS 后若落在 /login，需重新打开此链接完成 SSO）
    BPM_ENTRY_URL = (
        "https://bpm.cmhktry.com/main/portal/ctp-affair/affairPendingCenter"
        "?portletTitle=%E5%BE%85%E8%BE%A6%E4%BA%8B%E9%A0%85"
    )

    # 应用配置
    APP_NAME = "itsr07195287674072066508260"
    ROOT_ENTITY_NAME = "com.seeyon.itsr07195287674072066508260.domain.entity.ITfuwuxuqiu"
    PAGE_URL = "ITfuwuxuqiuxiangqing"
    PAGE_GUID = "-5702948354103621860"
    TEMPLATE_ID = "1214511312462186257"
    
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

        # Persist initial state for web multi-step flow (best-effort)
        self._persist_state()

    def _persist_state(self):
        """
        Best-effort: persist current session state into Django cache so that
        polling / step transitions work across multiple web workers.
        """
        def _debug(msg):
            try:
                with open("/tmp/itsr_close_debug.log", "a") as f:
                    import datetime
                    f.write(f"{datetime.datetime.now()} {msg}\n")
                    f.flush()
            except:
                pass
        
        if not _cache_enabled():
            _debug(f"[{self.session_id}] _persist_state: cache not enabled!")
            return
        try:
            _debug(f"[{self.session_id}] _persist_state: saving status={self.status.value}")
            _cache_update_state(
                self.session_id,
                ticket_numbers=self.ticket_numbers,
                update_db=bool(self.update_db),
                created_at=float(self.created_at),
                status=self.status.value,
                error=str(self.error or ""),
                results=_results_to_state_list(self.results),
            )
            # Verify it was written
            verify = _cache_get_state(self.session_id)
            if verify:
                _debug(f"[{self.session_id}] _persist_state: verified status={verify.get('status')}")
            else:
                _debug(f"[{self.session_id}] _persist_state: verification FAILED - cache empty!")
        except Exception as e:
            _debug(f"[{self.session_id}] persist_state failed: {e}")

    def _set_status(self, status: SessionStatus, error: str = ""):
        with self._lock:
            self.status = status
            if error:
                self.error = error
        self._persist_state()

    def _append_result(self, result: "TicketCloseResult"):
        with self._lock:
            self.results.append(result)
        self._persist_state()

    def _wait_for_sms_code(self, timeout: int = 300) -> bool:
        """
        Wait for SMS code.

        - In web multi-worker mode: poll Django cache for sms_code written by step 3.
        - Fallback: use the in-process event (legacy CLI/testing).
        """
        # Prefer cache coordination if available.
        if _cache_enabled():
            start = time.time()
            while time.time() - start < timeout:
                if _cache_is_cancelled(self.session_id):
                    self._set_status(SessionStatus.EXPIRED, "会话已取消")
                    return False
                code = _cache_get_sms_code(self.session_id)
                if code:
                    with self._lock:
                        self._sms_code = code
                    return True
                time.sleep(0.5)
            return False

        # Legacy path
        return bool(self._sms_event.wait(timeout=timeout))
    
    def submit_credentials(self, username: str, password: str, timeout: int = 600) -> Tuple[bool, str]:
        """
        提交账号密码，启动登录流程
        
        Args:
            username: 用户名
            password: 密码
            timeout: 等待超时（秒）；SSO+BPM 较慢时需足够长（默认 10 分钟）
        
        Returns:
            (success, message)
            - success=True, message="" 表示需要验证码
            - success=True, message="NO_SMS_REQUIRED" 表示无需验证码，已自动开始关单
            - success=False, message=错误信息
        """
        with self._lock:
            if self.status != SessionStatus.WAITING_CREDENTIALS:
                return False, f"状态错误: {self.status.value}"
            self._username = username
            self._password = password
        self._persist_state()
        
        # 启动登录线程
        self._thread = threading.Thread(target=self._login_and_close_flow, daemon=True)
        self._thread.start()
        
        # 通知线程开始
        self._credentials_event.set()
        
        # 等待到达验证码页面或直接登录成功
        import sys
        start_time = time.time()
        print(f"[{self.session_id}] submit_credentials: waiting for status change, current={self.status.value}", file=sys.stderr, flush=True)
        while time.time() - start_time < timeout:
            with self._lock:
                if self.status == SessionStatus.WAITING_SMS:
                    print(f"[{self.session_id}] submit_credentials: detected WAITING_SMS, persisting to cache", file=sys.stderr, flush=True)
                    # Ensure cache is updated before returning
                    self._persist_state()
                    print(f"[{self.session_id}] submit_credentials: returning True for SMS flow", file=sys.stderr, flush=True)
                    return True, ""
                # 无需验证码：认证完成后状态才会变为 NO_SMS_REQUIRED/CLOSING/SUCCESS
                if self.status in (SessionStatus.NO_SMS_REQUIRED, SessionStatus.CLOSING, SessionStatus.SUCCESS):
                    print(f"[{self.session_id}] submit_credentials: detected {self.status.value}, no SMS needed", file=sys.stderr, flush=True)
                    # Ensure cache is updated before returning
                    self._persist_state()
                    return True, "NO_SMS_REQUIRED"
                if self.status == SessionStatus.ERROR:
                    print(f"[{self.session_id}] submit_credentials: detected ERROR: {self.error}", file=sys.stderr, flush=True)
                    self._persist_state()
                    return False, self.error
            time.sleep(0.3)
        
        with self._lock:
            self.status = SessionStatus.ERROR
            self.error = "登录超时"
        self._persist_state()
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
        self._persist_state()
        
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
        """取消会话（仅用于中途取消，已完成的会话无需调用）"""
        # 检查是否已经是终态，避免死锁
        if self.status in (SessionStatus.SUCCESS, SessionStatus.ERROR, SessionStatus.EXPIRED):
            return
        
        with self._lock:
            if self.status in (SessionStatus.SUCCESS, SessionStatus.ERROR, SessionStatus.EXPIRED):
                return
            self.status = SessionStatus.EXPIRED
            self.error = "会话已取消"
        self._persist_state()
        
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
        self._persist_state()
    
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
            self._persist_state()
            
            # 执行 Playwright 登录，返回是否需要验证码
            needs_sms = self._do_playwright_login()
            if needs_sms is None:
                # 登录失败
                return
            
            if needs_sms:
                # 需要验证码流程
                def _debug(msg):
                    try:
                        with open("/tmp/itsr_close_debug.log", "a") as f:
                            import datetime
                            f.write(f"{datetime.datetime.now()} {msg}\n")
                            f.flush()
                    except:
                        pass
                _debug(f"[{self.session_id}] THREAD: needs_sms=True, setting WAITING_SMS...")
                with self._lock:
                    self.status = SessionStatus.WAITING_SMS
                    self.error = ""
                    # IMPORTANT: persist to cache while holding lock, so the main thread
                    # sees cache updated before it returns to caller.
                    self._persist_state()
                _debug(f"[{self.session_id}] THREAD: WAITING_SMS set and persisted to cache")
                logger.info(f"[{self.session_id}] 需要验证码，等待输入...")
                
                # 等待验证码（5分钟超时）
                if not self._wait_for_sms_code(timeout=300):
                    with self._lock:
                        self.status = SessionStatus.EXPIRED
                        self.error = "验证码等待超时"
                    self._persist_state()
                    self.cleanup()
                    return
                
                with self._lock:
                    if self.status == SessionStatus.EXPIRED:
                        return
                
                # 提交验证码并获取认证
                if not self._do_submit_sms():
                    return
            else:
                # 无需验证码流程
                logger.info(f"[{self.session_id}] 无需验证码，等待认证...")
                
                # 等待登录重定向完成并获取认证
                if not self._wait_for_auth_complete():
                    return
                
                # 认证成功后设置状态
                with self._lock:
                    self.status = SessionStatus.NO_SMS_REQUIRED
                    self.error = ""
                logger.info(f"[{self.session_id}] ✅ 认证成功（无需验证码）")
                self._persist_state()
            
            # 执行关单
            with self._lock:
                self.status = SessionStatus.CLOSING
                self.error = ""
            logger.info(f"[{self.session_id}] 开始关闭 {len(self.ticket_numbers)} 个工单...")
            self._persist_state()
            
            self._do_close_tickets()
            
            # 根据结果设置状态和日志
            success_count = sum(1 for r in self.results if r.success)
            fail_count = sum(1 for r in self.results if not r.success)
            
            with self._lock:
                self.status = SessionStatus.SUCCESS
                self.error = ""
            self._persist_state()
            
            if fail_count == 0:
                logger.info(f"[{self.session_id}] ✅ 关单完成，全部成功 ({success_count}个)")
            elif success_count == 0:
                logger.warning(f"[{self.session_id}] ❌ 关单完成，全部失败 ({fail_count}个)")
            else:
                logger.info(f"[{self.session_id}] ⚠️ 关单完成，成功 {success_count}个，失败 {fail_count}个")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] 流程异常: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = str(e)
            self._persist_state()
        
        finally:
            self.cleanup()
    
    def _do_playwright_login(self) -> Optional[bool]:
        """
        执行 Playwright 登录，自动判断是否需要验证码
        
        Returns:
            True: 需要验证码
            False: 无需验证码，已直接登录成功
            None: 登录失败
        """
        try:
            from playwright.sync_api import sync_playwright
            
            logger.info(f"[{self.session_id}] 启动 Playwright...")
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            
            logger.info(f"[{self.session_id}] 访问 BPM...")
            self._page.goto(self.BPM_ENTRY_URL, wait_until='domcontentloaded', timeout=30000)
            
            logger.info(f"[{self.session_id}] 等待 CAS (hk.chinamobile 或 cmhktry)...")
            self._page.wait_for_url(_CAS_LOGIN_URL_RE, timeout=60000)
            
            logger.info(f"[{self.session_id}] 填写凭据: {self._username}")
            self._page.fill('input[name="username"]', self._username)
            self._page.fill('input[name="password"]', self._password)
            self._page.click('button[type="submit"], input[type="submit"]')
            
            logger.info(f"[{self.session_id}] 等待页面跳转...")
            self._page.wait_for_load_state('domcontentloaded', timeout=15000)
            
            # 自动判断是否需要验证码
            needs_sms = self._check_if_sms_required()
            
            if needs_sms:
                logger.info(f"[{self.session_id}] 检测到需要验证码")
            else:
                logger.info(f"[{self.session_id}] 检测到无需验证码，已直接登录")
                # 等待页面完全加载以获取认证信息
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
            self._persist_state()
            self.cleanup()
            return None
    
    def _check_if_sms_required(self) -> bool:
        """
        检查是否需要短信验证码
        
        判断逻辑：
        1. 检查当前 URL 主机名 - 如果已跳转到 BPM，说明不需要验证码
        2. 检查页面是否存在验证码输入框
        3. 如果还在 CAS 页面且有验证码输入框，说明需要验证码
        
        Returns:
            True: 需要验证码
            False: 不需要验证码
        """
        try:
            current_url = self._page.url
            logger.info(f"[{self.session_id}] 当前URL: {current_url}")
            
            # 解析 URL 获取主机名
            parsed_url = urlparse(current_url)
            hostname = parsed_url.netloc  # 获取主机名部分
            logger.info(f"[{self.session_id}] 主机名: {hostname}")
            
            # 方法1: BPM 主机 — 但 /login 不是已登录门户，需等 SSO 或后续恢复
            if "bpm.cmhktry.com" in hostname:
                if _bpm_is_unauthenticated_login_url(current_url):
                    logger.info(
                        f"[{self.session_id}] 当前为 BPM /login，尝试 CAS/统一认证入口…"
                    )
                    for _ in range(3):
                        if not _bpm_is_unauthenticated_login_url(self._page.url):
                            break
                        if not _try_bpm_sso_from_login_page(self._page, self.session_id):
                            break
                        self._page.wait_for_timeout(2000)
                    current_url = self._page.url
                    if _bpm_is_unauthenticated_login_url(current_url):
                        logger.info(
                            f"[{self.session_id}] 仍在 BPM /login，等待自动跳转…"
                        )
                        try:
                            self._page.wait_for_function(
                                """() => {
                                  const h = window.location.hostname || '';
                                  const p = window.location.pathname.toLowerCase() || '';
                                  if (!h.includes('bpm.cmhktry.com')) return true;
                                  return p !== '/login' && !p.startsWith('/login/');
                                }""",
                                timeout=45000,
                            )
                        except Exception as e:
                            logger.warning(
                                f"[{self.session_id}] 等待离开 BPM /login: {e}"
                            )
                    current_url = self._page.url
                    hostname = urlparse(current_url).netloc
                if "bpm.cmhktry.com" in hostname and not _bpm_is_unauthenticated_login_url(
                    current_url
                ):
                    logger.info(f"[{self.session_id}] 已跳转到BPM站点，无需验证码")
                    return False
            
            # 方法2: 检查是否还在 CAS 页面（两种 IdP 主机名）
            if "ncas.hk.chinamobile.com" in hostname or "ncas.cmhktry.com" in hostname:
                # 检查页面上是否有验证码输入框
                sms_indicators = [
                    '#code_input1',           # 6位验证码输入框
                    '#sms_token',             # 验证码token
                    'input[name="token"]',    # token输入框
                    '.sms-code-input',        # 可能的验证码输入样式
                    '#sendSmsBtn',            # 发送验证码按钮
                ]
                
                for selector in sms_indicators:
                    elem = self._page.query_selector(selector)
                    if elem:
                        logger.info(f"[{self.session_id}] 检测到验证码元素: {selector}")
                        return True
                
                # 检查页面文本是否包含验证码相关内容
                page_text = self._page.text_content('body') or ""
                sms_keywords = ['验证码', '短信验证', 'SMS', 'verification code']
                for keyword in sms_keywords:
                    if keyword.lower() in page_text.lower():
                        logger.info(f"[{self.session_id}] 页面包含验证码关键词: {keyword}")
                        return True
                
                # 还在 CAS 但没有明确的验证码标识，等待一下看是否会跳转
                logger.info(f"[{self.session_id}] 在CAS页面，等待可能的跳转...")
                try:
                    # 等待URL主机名变为BPM（不是作为参数包含）
                    self._page.wait_for_function(
                        "() => window.location.hostname.includes('bpm.cmhktry.com')",
                        timeout=5000
                    )
                    logger.info(f"[{self.session_id}] 成功跳转到BPM，无需验证码")
                    return False
                except:
                    # 没有跳转，再次检查验证码元素
                    for selector in sms_indicators:
                        elem = self._page.query_selector(selector)
                        if elem:
                            return True
                    # 默认需要验证码（保守策略）
                    logger.info(f"[{self.session_id}] 无法确定，默认需要验证码")
                    return True
            
            # 其他情况，检查是否有验证码输入框
            code_input = self._page.query_selector('#code_input1')
            if code_input:
                return True
            
            # 默认不需要验证码
            return False
            
        except Exception as e:
            logger.warning(f"[{self.session_id}] 检查验证码需求时出错: {e}")
            # 出错时保守处理，假设需要验证码
            return True
    
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
                self._persist_state()
                return False
            
            logger.info(f"[{self.session_id}] ✅ 获取认证成功")
            return True
            
        except Exception as e:
            logger.error(f"[{self.session_id}] 提交验证码失败: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = f"验证失败: {e}"
            self._persist_state()
            return False
    
    def _extract_auth(self):
        """提取认证信息（合并全局与各域 cookies，含 HttpOnly）"""
        merged = {}
        try:
            for c in self._context.cookies():
                merged[c['name']] = c['value']
            for url in (
                'https://bpm.cmhktry.com/',
                'https://bpm.cmhktry.com',
            ):
                try:
                    for c in self._context.cookies(urls=[url]):
                        merged[c['name']] = c['value']
                except Exception:
                    pass
        except Exception:
            pass
        if merged.get('SY_ACCESS_TOKEN'):
            self._access_token = merged['SY_ACCESS_TOKEN']
        if merged.get('SY_UID'):
            self._uid = merged['SY_UID']

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
            except Exception:
                pass

    def _wait_for_auth_complete(self) -> bool:
        """
        等待认证完成（无需验证码的情况）。
        注意：``https://bpm.cmhktry.com/login`` 不是已登录状态，不能匹配泛泛的 bpm/**。
        """
        try:
            entry = self.BPM_ENTRY_URL
            logger.info(f"[{self.session_id}] 等待 SSO / token… URL={self._page.url!r}")

            # 若停在 BPM 登录页，重新打开待办链接触发 SSO（最多 2 次）
            for recovery in range(2):
                if _bpm_is_unauthenticated_login_url(self._page.url):
                    for _ in range(2):
                        if not _bpm_is_unauthenticated_login_url(self._page.url):
                            break
                        if not _try_bpm_sso_from_login_page(self._page, self.session_id):
                            break
                        self._page.wait_for_timeout(2000)
                if _bpm_is_unauthenticated_login_url(self._page.url):
                    logger.warning(
                        f"[{self.session_id}] BPM 仍为 /login，重新进入待办链接 "
                        f"(recovery={recovery + 1}/2)"
                    )
                    try:
                        self._page.goto(entry, wait_until='domcontentloaded', timeout=60000)
                        self._page.wait_for_timeout(2000)
                    except Exception as e:
                        logger.warning(f"[{self.session_id}] 重新打开待办失败: {e}")

                t_end = time.time() + 120
                while time.time() < t_end:
                    self._extract_auth()
                    if self._access_token and self._uid:
                        logger.info(f"[{self.session_id}] 认证获取成功: uid={self._uid}")
                        return True
                    cur = self._page.url
                    if 'bpm.cmhktry.com' in cur and not _bpm_is_unauthenticated_login_url(cur):
                        break
                    self._page.wait_for_timeout(500)
                else:
                    if recovery == 0:
                        continue
                    break

                self._extract_auth()
                if self._access_token and self._uid:
                    logger.info(f"[{self.session_id}] 认证获取成功: uid={self._uid}")
                    return True
                break

            # 已进入非 /login 的 BPM 或仍需等待 XHR 发 token
            try:
                with self._page.expect_response(
                    lambda r: 'refresh-token' in r.url and r.status == 200,
                    timeout=90000,
                ):
                    self._page.wait_for_load_state('networkidle', timeout=90000)
            except Exception:
                try:
                    self._page.wait_for_load_state('networkidle', timeout=45000)
                except Exception:
                    self._page.wait_for_timeout(3000)

            for attempt in range(180):
                self._extract_auth()
                if self._access_token and self._uid:
                    logger.info(f"[{self.session_id}] 认证获取成功: uid={self._uid}")
                    return True
                if attempt > 0 and attempt % 20 == 0:
                    logger.info(
                        f"[{self.session_id}] 仍等待 token… attempt={attempt} "
                        f"url={self._page.url!r}"
                    )
                self._page.wait_for_timeout(500)

            final_u = self._page.url
            if _bpm_is_unauthenticated_login_url(final_u):
                msg = (
                    'BPM 仍停留在登录页 (/login)，无法获取认证。'
                    '请在浏览器中打开 BPM 待办确认是否有「统一认证/CAS」入口；'
                    '若账号无权限或 IdP 变更，请联系管理员。'
                )
            else:
                msg = '认证超时'
            logger.error(f"[{self.session_id}] {msg} 最终 URL={final_u!r}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = msg
            self._persist_state()
            return False

        except Exception as e:
            logger.error(f"[{self.session_id}] 认证失败: {e}")
            with self._lock:
                self.status = SessionStatus.ERROR
                self.error = f'认证失败: {e}'
            self._persist_state()
            return False
    
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
            self._append_result(result)
            
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
            logger.info(f"[{self.session_id}] 查询工单: {ticket_number}")
            
            # 通过事项列表获取工单详情（包含 caseId, affairId 等关键字段）
            detail = self._get_ticket_detail(session, ticket_number)
            if not detail:
                return TicketCloseResult(ticket_number, False, "获取工单详情失败（工单不存在或无权限）")
            
            logger.info(f"[{self.session_id}] 工单详情: caseId={detail.get('caseId')}, "
                       f"affairId={detail.get('affairId')}, status={detail.get('yewuzhuangtai')}")
            
            # 获取子表数据（处理明细）
            zibiao = self._get_zibiao(session, detail)
            logger.info(f"[{self.session_id}] 子表数量: {len(zibiao)}")
            
            # 执行关单
            success, msg = self._do_close(session, detail, zibiao)
            return TicketCloseResult(ticket_number, success, msg)
            
        except Exception as e:
            logger.error(f"[{self.session_id}] 关单异常: {e}")
            return TicketCloseResult(ticket_number, False, str(e))
    
    def _get_ticket_detail(self, session: requests.Session, ticket_number: str) -> Optional[Dict]:
        """
        通过事项列表API查询工单详情
        
        返回包含 caseId, affairId, formRecordId, permissionId 等关键字段的字典
        """
        # 使用事项列表 API 搜索工单（参考 itsr_auto_close.py）
        payload = {
            "filterPlanGuids": ["1164050706911494756"],
            "searchParams": {
                "searchParam": {
                    "LIKE_ShixiangDto_iTSRbianhao": ticket_number  # 正确的搜索参数格式
                },
                "logicalOperator": "AND",
                "sortSettings": [],
                "expressionValues": {},
                "one2OneEntityRelationsV2": []
            },
            "pageInfo": {
                "pageNumber": 1,
                "pageSize": 10,
                "pages": 1,
                "total": 0,
                "needTotal": True
            }
        }
        
        try:
            resp = session.post(self.LIST_ENDPOINT, json=payload, timeout=30)
            logger.info(f"[{self.session_id}] 列表API响应: HTTP {resp.status_code}, 长度: {len(resp.text)}")
            
            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] HTTP错误: {resp.status_code}, 响应: {resp.text[:500]}")
                return None
            
            try:
                data = resp.json()
                logger.debug(f"[{self.session_id}] 列表API响应内容: {str(data)[:500]}")
            except Exception as json_err:
                logger.error(f"[{self.session_id}] JSON解析失败: {json_err}, 响应内容: {resp.text[:500]}")
                return None
            
            if data is None:
                logger.error(f"[{self.session_id}] API返回空响应")
                return None
            
            api_status = data.get('status')
            api_message = data.get('message', '')
            
            # 安全地获取 content，避免 NoneType 错误
            data_obj = data.get('data')
            if data_obj is None:
                logger.error(f"[{self.session_id}] API响应缺少data字段，完整响应: {str(data)[:500]}")
                return None
            
            content = data_obj.get('content', []) if isinstance(data_obj, dict) else []
            
            logger.info(f"[{self.session_id}] 列表查询: status={api_status}, message='{api_message}', 数量={len(content)}")
            
            if api_status == 0 and content:
                # 查找匹配的工单
                for ticket in content:
                    if ticket.get('iTSRbianhao') == ticket_number:
                        logger.info(f"[{self.session_id}] 找到工单: caseId={ticket.get('caseId')}, affairId={ticket.get('affairId')}")
                        return ticket
                logger.warning(f"[{self.session_id}] 工单编号不匹配: {ticket_number}")
            
            if api_status != 0:
                logger.warning(f"[{self.session_id}] API错误: {api_message}")
            else:
                logger.warning(f"[{self.session_id}] 工单不存在: {ticket_number}")
            
            return None
        except Exception as e:
            logger.error(f"[{self.session_id}] 查询工单异常: {e}")
            return None
    
    def _get_zibiao(self, session: requests.Session, detail: Dict) -> List[Dict]:
        """
        通过 GraphQL 获取子表数据 (处理明细) - 参考 itsr_auto_close.py
        
        Args:
            detail: 工单详情（包含 caseId, affairId, permissionId 等）
        
        Returns:
            包含子表ID信息的列表，或空列表
        """
        case_id = detail.get('caseId')
        affair_id = detail.get('affairId')
        permission_id = detail.get('permissionId', '1111312494347391345')
        form_record_id = detail.get('formRecordId')
        template_id = detail.get('templateId', self.TEMPLATE_ID)
        
        if not all([case_id, affair_id, form_record_id]):
            logger.warning(f"[{self.session_id}] 缺少必要参数，无法获取子表")
            return []
        
        # GraphQL 查询详情（包含子表）
        graphql_query = {
            "query": """mutation graphqlLoader ($params0: bpmSummarySelectDetailPostInputBody) { 
  data0: bpmSummarySelectDetailPost(body: $params0) { code data { content } message status } }""",
            "variables": {
                "params0": {
                    "affairId": str(affair_id),
                    "caseId": str(case_id),
                    "detailType": "SHARE",
                    "permissionId": str(permission_id),
                    "templateId": str(template_id),
                    "pageGuid": self.PAGE_GUID,
                    "appName": self.APP_NAME,
                    "rootEntityName": self.ROOT_ENTITY_NAME,
                    "pageUrl": self.PAGE_URL,
                    "pageType": "PC",
                    "systemSettingCodes": ["COMMENTS_INPUT_BOX_SETTING", "ACTIVITY_INFORM_OPERATE", 
                                          "AFFAIR_CONSULT_OPINION", "ACTIVITY_ADD_OPERATE", "BPM_OPINION"]
                }
            }
        }
        
        try:
            resp = session.post(
                f"{self.GRAPHQL_ENDPOINT}?bpmSummarySelectDetailPost",
                json=graphql_query,
                timeout=30
            )
            
            if resp.status_code != 200:
                logger.warning(f"[{self.session_id}] GraphQL HTTP错误: {resp.status_code}")
                return []
            
            data = resp.json()
            
            # 检查 GraphQL 响应状态
            data0 = data.get('data', {}).get('data0', {})
            gql_status = data0.get('status')
            gql_message = data0.get('message', '')
            logger.info(f"[{self.session_id}] GraphQL响应: status={gql_status}, message={gql_message}")
            
            if gql_status != 0:
                logger.warning(f"[{self.session_id}] GraphQL查询失败: {gql_message}")
                return []
            
            detail_content = data0.get('data', {}).get('content', {})
            
            # 调试：打印详情内容的顶层键
            if detail_content:
                logger.debug(f"[{self.session_id}] 详情内容键: {list(detail_content.keys())[:10]}")
            
            # 方法1：优先从 nodeGroupId 获取（参考 itsr_auto_close.py）
            node_group_id = detail_content.get("nodeGroupId", "")
            if node_group_id:
                logger.info(f"[{self.session_id}] 从 nodeGroupId 获取子表ID: {node_group_id}")
                return [{"id": node_group_id, "__key": node_group_id}]
            
            # 方法2：从 loadPageDto.data.chulimingxiDtoList 获取
            load_page_dto = detail_content.get("loadPageDto", {})
            form_data = load_page_dto.get("data", {})
            if form_data:
                chulimingxi_list = form_data.get("chulimingxiDtoList", [])
                if chulimingxi_list:
                    logger.info(f"[{self.session_id}] 从 loadPageDto 获取子表，数量: {len(chulimingxi_list)}")
                    return chulimingxi_list
            
            # 方法3：从 bpmCaseDto.formData 获取
            bpm_case = detail_content.get("bpmCaseDto", {})
            if bpm_case.get("formData"):
                try:
                    import json as json_module
                    fd = bpm_case["formData"]
                    if isinstance(fd, str):
                        fd = json_module.loads(fd)
                    chulimingxi_list = fd.get("chulimingxiDtoList", [])
                    if chulimingxi_list:
                        logger.info(f"[{self.session_id}] 从 bpmCaseDto.formData 获取子表，数量: {len(chulimingxi_list)}")
                        return chulimingxi_list
                except Exception as e:
                    logger.debug(f"[{self.session_id}] 解析 bpmCaseDto.formData 失败: {e}")
            
            # 方法4：从 formDto.formData 获取
            form_dto = detail_content.get("formDto", {})
            if form_dto:
                fd = form_dto.get("formData", {})
                chulimingxi_list = fd.get("chulimingxiDtoList", [])
                if chulimingxi_list:
                    logger.info(f"[{self.session_id}] 从 formDto 获取子表，数量: {len(chulimingxi_list)}")
                    return chulimingxi_list
            
            logger.warning(f"[{self.session_id}] 未能从详情中提取子表数据")
            return []
            
        except Exception as e:
            logger.error(f"[{self.session_id}] 获取子表异常: {e}")
            return []
    
    def _do_close(self, session: requests.Session, detail: Dict, zibiao: List[Dict]) -> Tuple[bool, str]:
        """
        执行关单 - 两步提交流程（参考 itsr_auto_close.py）
        
        Args:
            detail: 工单详情（包含 caseId, affairId, formRecordId, permissionId 等）
            zibiao: 子表数据（处理明细）
        """
        # 从详情中提取必要字段
        case_id = str(detail.get('caseId', ''))
        affair_id = str(detail.get('affairId', ''))
        form_record_id = str(detail.get('formRecordId', ''))
        permission_id = str(detail.get('permissionId', '1111312494347391345'))
        
        if not all([case_id, affair_id, form_record_id]):
            logger.error(f"[{self.session_id}] 缺少必要参数: caseId={case_id}, affairId={affair_id}, "
                        f"formRecordId={form_record_id}")
            return False, "缺少必要的工单参数"
        
        # 获取子表ID（优先从 zibiao 列表获取，否则使用 form_record_id）
        zibiaoshuju_id = ""
        if zibiao:
            zibiaoshuju_id = str(zibiao[0].get('id', zibiao[0].get('__key', '')))
        
        if not zibiaoshuju_id:
            logger.warning(f"[{self.session_id}] 未获取到子表ID，尝试使用默认值")
            zibiaoshuju_id = form_record_id  # 回退使用 form_record_id
        
        # 生成请求ID
        request_id = f"COLLOABORATION_{int(time.time() * 1000)}"
        uid = self._uid if hasattr(self, '_uid') and self._uid else ""
        
        # ========== 第一步提交：带表单数据 ==========
        first_payload = {
            "changeNodeRequestDtos": [],
            "affairId": affair_id,
            "formData": {
                "chulimingxiDtoList": [
                    {
                        "wentijieda": "Done.",
                        "jiejuejiyufangcuoshi": "Done.",
                        "__key": zibiaoshuju_id,
                        "actionType": "UPDATE",
                        "id": zibiaoshuju_id,
                        "positionIndex": zibiaoshuju_id
                    }
                ],
                "__key": form_record_id,
                "actionType": "UPDATE",
                "id": form_record_id,
                "extraParamMap": {
                    "formPermissionId": f"{permission_id}_PC"
                }
            },
            "preMatchRequestDto": {
                "oneHandlerMatchNeedPop": False
            },
            "bpmOpinionDto": {
                "id": None,
                "objectId": case_id,
                "subObjectId": affair_id,
                "content": "Done.",
                "richContent": "",
                "attachmentStorageIds": [],
                "opinion": "SUBMIT",
                "showPerson": uid,
                "extra": {
                    "hidden": False,
                    "opinionHidden": uid
                },
                "userIds": [],
                "createUserName": "",
                "hidden": False,
                "operationCaption": '{"zh_CN":"提交","en":"Submit"}'
            },
            "evaluationRecordDtoList": [],
            "informAddSelectPeoples": "[]",
            "requestId": request_id
        }
        
        logger.info(f"[{self.session_id}] 执行第一次提交: caseId={case_id}, affairId={affair_id}")
        
        try:
            resp = session.post(self.SUBMIT_ENDPOINT, json=first_payload, timeout=30)
            logger.info(f"[{self.session_id}] 第一次Submit响应: HTTP {resp.status_code}")
            
            if resp.status_code != 200:
                logger.error(f"[{self.session_id}] HTTP错误: {resp.status_code}, 响应: {resp.text[:500]}")
                return False, f"HTTP错误: {resp.status_code}"
            
            first_result = resp.json()
            status = first_result.get('status')
            code = first_result.get('code', '')
            message = first_result.get('message', '')
            
            logger.info(f"[{self.session_id}] 第一次Submit结果: status={status}, code={code}, message={message}")
            
            if status != 0:
                logger.error(f"[{self.session_id}] ❌ 第一次提交失败: {message}")
                return False, message or "第一次提交失败"
            
            # ========== 检查是否需要第二次提交 ==========
            pre_match_response = first_result.get("data", {}).get("content", {}).get("preMatchResponseDto", {})
            condition_map = pre_match_response.get("conditionMatchResultDtoMap", {})
            
            if condition_map:
                # 需要第二次确认提交
                logger.info(f"[{self.session_id}] 检测到条件匹配，执行第二次确认提交...")
                
                conditions_of_links = {key: False for key in condition_map.keys()}
                
                second_payload = {
                    "changeNodeRequestDtos": [],
                    "affairId": affair_id,
                    "formData": {
                        "id": form_record_id,
                        "extraParamMap": {
                            "formPermissionId": f"{permission_id}_PC"
                        }
                    },
                    "preMatchRequestDto": {
                        "conditionsOfLinks": conditions_of_links,
                        "selectedPeoplesOfNodes": {},
                        "nodeSubLicenseMap": {}
                    },
                    "formDataMap": {},
                    "bpmOpinionDto": {
                        "id": None,
                        "objectId": case_id,
                        "subObjectId": affair_id,
                        "content": "Done.",
                        "richContent": "",
                        "attachmentStorageIds": [],
                        "opinion": "SUBMIT",
                        "showPerson": uid,
                        "extra": {
                            "hidden": False,
                            "opinionHidden": uid
                        },
                        "userIds": [],
                        "createUserName": "",
                        "hidden": False,
                        "operationCaption": '{"zh_CN":"提交","en":"Submit"}'
                    },
                    "evaluationRecordDtoList": [],
                    "informAddSelectPeoples": "[]",
                    "requestId": request_id
                }
                
                resp = session.post(self.SUBMIT_ENDPOINT, json=second_payload, timeout=30)
                logger.info(f"[{self.session_id}] 第二次Submit响应: HTTP {resp.status_code}")
                
                if resp.status_code != 200:
                    logger.error(f"[{self.session_id}] HTTP错误: {resp.status_code}")
                    return False, f"HTTP错误: {resp.status_code}"
                
                second_result = resp.json()
                status = second_result.get('status')
                code = second_result.get('code', '')
                message = second_result.get('message', '')
                
                logger.info(f"[{self.session_id}] 第二次Submit结果: status={status}, code={code}, message={message}")
                
                if status == 0:
                    logger.info(f"[{self.session_id}] ✅ 关单成功（两步提交）")
                    return True, "关闭成功"
                else:
                    logger.error(f"[{self.session_id}] ❌ 第二次提交失败: {message}")
                    return False, message or "第二次提交失败"
            else:
                # 一次提交即成功
                logger.info(f"[{self.session_id}] ✅ 关单成功（一步提交）")
                return True, "关闭成功"
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Submit异常: {e}")
            return False, str(e)


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
            # 只有未完成的会话才需要 cancel
            if session.status not in (SessionStatus.SUCCESS, SessionStatus.ERROR, SessionStatus.EXPIRED):
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
    # Preferred in web deployments: cache-backed state so it works across workers.
    if _cache_enabled():
        session_id = str(uuid.uuid4())[:8]
        now = time.time()
        state = {
            "session_id": session_id,
            "ticket_numbers": ticket_numbers or [],
            "update_db": bool(update_db),
            "created_at": now,
            "updated_at": now,
            "status": SessionStatus.WAITING_CREDENTIALS.value,
            "error": "",
            "results": [],
        }
        logger.info(f"[{session_id}] create_close_session: cache enabled, creating state for {len(ticket_numbers)} tickets")
        _cache_set_state(session_id, state)
        # Verify it was written
        verify = _cache_get_state(session_id)
        if verify:
            logger.info(f"[{session_id}] create_close_session: state written and verified in cache")
        else:
            logger.error(f"[{session_id}] create_close_session: WARNING - state write failed verification!")
        return session_id

    # Fallback: legacy in-memory manager (single-process friendly).
    return get_manager().create_session(ticket_numbers, update_db)


def submit_credentials(session_id: str, username: str, password: str) -> Tuple[bool, str]:
    """
    提交账号密码，启动登录流程（自动判断是否需要验证码）
    
    Args:
        session_id: 会话ID
        username: 用户名
        password: 密码
    
    Returns:
        (success, message)
        - success=True, message="" 表示需要验证码，等待输入
        - success=True, message="NO_SMS_REQUIRED" 表示无需验证码，已自动开始关单
        - success=False, message=错误信息 表示登录失败
    
    Example:
        success, msg = submit_credentials(session_id, "PY0121", "password")
        if success:
            if msg == "NO_SMS_REQUIRED":
                print("无需验证码，自动登录成功，正在关单...")
                # 直接等待关单结果
                result = wait_close_result(session_id)
            else:
            print("请输入验证码")
                # 需要调用 submit_sms_code
        else:
            print(f"登录失败: {msg}")
    """
    # Cache-backed mode: create executor locally, coordinate state via cache.
    import sys
    if _cache_enabled():
        print(f"[{session_id}] submit_credentials: cache enabled, fetching state...", file=sys.stderr, flush=True)
        state = _cache_get_state(session_id)
        if not state:
            print(f"[{session_id}] submit_credentials: state not found in cache!", file=sys.stderr, flush=True)
            return False, "会话不存在或已过期"

        status = str(state.get("status", "")).strip()
        print(f"[{session_id}] submit_credentials: current status={status}", file=sys.stderr, flush=True)
        if status and status != SessionStatus.WAITING_CREDENTIALS.value:
            return False, f"状态错误: {status}"

        # Best-effort cross-worker start lock to avoid duplicate runners.
        if not _cache_try_mark_started(session_id):
            print(f"[{session_id}] submit_credentials: already started, rejecting duplicate", file=sys.stderr, flush=True)
            return False, "会话已开始处理，请勿重复提交"

        ticket_numbers = list(state.get("ticket_numbers") or [])
        update_db = bool(state.get("update_db", True))
        print(f"[{session_id}] submit_credentials: creating CloseSession with {len(ticket_numbers)} tickets", file=sys.stderr, flush=True)

        # Start a local CloseSession runner thread; it will persist progress to cache.
        session = CloseSession(session_id, ticket_numbers, update_db=update_db)
        result = session.submit_credentials(username, password)
        print(f"[{session_id}] submit_credentials: returning result={result}", file=sys.stderr, flush=True)
        return result

    # Legacy in-memory mode.
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
    # Cache-backed mode: store SMS code and wait for runner completion via cache.
    if _cache_enabled():
        state = _cache_get_state(session_id)
        if not state:
            return CloseSessionResult(error="会话不存在或已过期")

        def _debug(msg):
            try:
                with open("/tmp/itsr_close_debug.log", "a") as f:
                    import datetime
                    f.write(f"{datetime.datetime.now()} {msg}\n")
                    f.flush()
            except:
                pass
        status = str(state.get("status", "")).strip()
        _debug(f"[{session_id}] submit_sms_code: cache status={status}, expecting={SessionStatus.WAITING_SMS.value}")
        if status != SessionStatus.WAITING_SMS.value:
            _debug(f"[{session_id}] submit_sms_code: STATUS MISMATCH! Returning error.")
            return CloseSessionResult(error=f"状态错误: {status or 'unknown'}")

        _cache_set_sms_code(session_id, sms_code)
        _cache_update_state(session_id, sms_submitted_at=time.time())

        start_time = time.time()
        timeout = 180
        while time.time() - start_time < timeout:
            cur = _cache_get_state(session_id)
            if not cur:
                return CloseSessionResult(error="会话不存在或已过期")

            cur_status = str(cur.get("status", "")).strip()
            cur_results = _state_to_result_list(cur.get("results", []))
            cur_error = str(cur.get("error", "") or "")

            if cur_status == SessionStatus.SUCCESS.value:
                return CloseSessionResult(success=True, results=cur_results, error=cur_error)
            if cur_status == SessionStatus.ERROR.value:
                return CloseSessionResult(success=False, results=cur_results, error=cur_error)
            if cur_status == SessionStatus.EXPIRED.value:
                return CloseSessionResult(success=False, results=cur_results, error=cur_error or "会话已过期")

            time.sleep(0.5)

        # Timed out waiting for completion
        return CloseSessionResult(error="关单超时", results=_state_to_result_list(state.get("results", [])))

    # Legacy in-memory mode.
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
    if _cache_enabled():
        _cache_set_cancelled(session_id)
        _cache_update_state(session_id, status=SessionStatus.EXPIRED.value, error="会话已取消")
        return

    get_manager().remove_session(session_id)


def get_session_status(session_id: str) -> Optional[str]:
    """
    获取会话状态
    
    Args:
        session_id: 会话ID
    
    Returns:
        状态字符串，如 "waiting_credentials", "waiting_sms", "closing", "no_sms_required" 等
        如果会话不存在返回 None
    
    Example:
        status = get_session_status(session_id)
        print(f"当前状态: {status}")
    """
    if _cache_enabled():
        state = _cache_get_state(session_id)
        if not state:
            return None
        status = state.get("status")
        return str(status) if status else None

    session = get_manager().get_session(session_id)
    if session:
        return session.status.value
    return None


def wait_close_result(session_id: str, timeout: int = 180) -> CloseSessionResult:
    """
    等待关单结果（用于无需验证码的情况）
    
    当 submit_credentials 返回 NO_SMS_REQUIRED 时，调用此函数等待关单完成
    """
    if _cache_enabled():
        state = _cache_get_state(session_id)
        if not state:
            return CloseSessionResult(error="会话不存在或已过期")

        start_time = time.time()
        while time.time() - start_time < timeout:
            cur = _cache_get_state(session_id)
            if not cur:
                return CloseSessionResult(error="会话不存在或已过期")

            cur_status = str(cur.get("status", "")).strip()
            cur_results = _state_to_result_list(cur.get("results", []))
            cur_error = str(cur.get("error", "") or "")

            if cur_status == SessionStatus.SUCCESS.value:
                return CloseSessionResult(success=True, results=cur_results, error=cur_error)
            if cur_status == SessionStatus.ERROR.value:
                return CloseSessionResult(success=False, results=cur_results, error=cur_error)
            if cur_status == SessionStatus.EXPIRED.value:
                return CloseSessionResult(success=False, results=cur_results, error=cur_error or "会话已过期")

            time.sleep(0.3)

        return CloseSessionResult(error="关单超时", results=_state_to_result_list(state.get("results", [])))

    session = get_manager().get_session(session_id)
    if not session:
        return CloseSessionResult(error="会话不存在或已过期")

    # 等待完成
    start_time = time.time()
    while time.time() - start_time < timeout:
        with session._lock:
            if session.status == SessionStatus.SUCCESS:
                result = CloseSessionResult(success=True, results=session.results)
                get_manager().remove_session(session_id)
                return result

            if session.status == SessionStatus.ERROR:
                result = CloseSessionResult(error=session.error, results=session.results)
                get_manager().remove_session(session_id)
                return result

            if session.status == SessionStatus.EXPIRED:
                result = CloseSessionResult(error="会话已过期", results=session.results)
                get_manager().remove_session(session_id)
                return result

        time.sleep(0.3)

    return CloseSessionResult(error="关单超时")


# ============================================================================
# 一站式关单函数（用于测试）
# ============================================================================

def close_tickets_interactive(ticket_numbers: List[str], update_db: bool = True) -> CloseSessionResult:
    """
    交互式关单（命令行测试用）
    
    自动判断是否需要验证码：
    - 如果账号需要验证码，会提示输入
    - 如果账号不需要验证码，会自动完成登录并关单
    
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
    
    print("正在登录...")
    success, msg = submit_credentials(session_id, username, password)
    
    if not success:
        print(f"❌ 登录失败: {msg}")
        return CloseSessionResult(error=msg)
    
    # 检查是否需要验证码
    if msg == "NO_SMS_REQUIRED":
        print("✅ 无需验证码，正在关闭工单...")
        result = wait_close_result(session_id)
    else:
        print("✅ 登录成功，需要验证码...")
    
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
