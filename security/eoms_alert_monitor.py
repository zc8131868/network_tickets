#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EOMS 工单监控告警脚本
- 使用手动填写的 SESSION 访问 NCOA
- 使用 Playwright 无头模式自动登录 EOMS（自动填写账号密码）
- 监控 NCOA 待办工单
- 从访问链接获取工单详情（instId 和 Issuedto）
- 发送飞书告警
"""

import os
import re
import json
import time
import asyncio
import logging
import threading
from datetime import datetime, timedelta

import requests
import urllib3
from requests.exceptions import ConnectionError, Timeout, RequestException
from playwright.async_api import async_playwright

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== 配置 ==========

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# EOMS/CAS 登录账号密码（请替换为您的实际凭证）
# ============================================================
EOMS_USERNAME = "p7869"
EOMS_PASSWORD = "Ericsson_5"

# SESSION 值（需要手动更新，从浏览器获取）
# 获取方式：浏览器登录 NCOA -> F12 -> Application -> Cookies -> SESSION
SESSION = "53b8743d-7c20-4620-bb93-0338c55cf77c"

# 飞书 Webhook URL
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/4a8d1b1e-eff4-4cca-890f-d70e236908d1"

# EOMS 登录状态缓存文件
EOMS_STORAGE_STATE_FILE = os.path.join(SCRIPT_DIR, "eoms_auth_state.json")

# 工号对照表（工号 -> 姓名）
# 格式: "工号": "中文名 英文名"
STAFF_ID_MAP = {
    "P7823": "郑伟 Mark ZHENG Wei",
    "P7117": "何智聰 Kobe HO Chi Chung",
    "P6898": "王经纬 Will WONG King Wai",
    "P3880" : "梁国锋 Benz LEUNG Kwok Fung",
    "P7030": "冼志辉 Anthony SIN Chi Fai",
    "P0148": "张世文 Simon CHEUNG Sai Man",
    "P7102": "陈国华 Howard CHEN Guohua",
    "P7218": "甘远恒 Hang KAM Yuen Hang",
    "P6534": "李春晓 Chris LI Chun Hiu",
    "P3759":"黎子敏 LAI Tsz Man",
    "P7055": "钟骏杰 Barnett ZHONG Junjie",
    "P7869": "郑程 ZHENG Cheng",
    "P4982": "龙剑云 Lucille LONG Jianyun",
    "P7104": "王英建 Kane WONG Ying Kin",
    "P6950": "吴适 Steven WU Shi",
    "p2561": "洪亮 Edward HUNG Leung",
    "p5882": "陈伟强 Kenny CHEN Weiqiang",
    "p7824": "柴征宇 Raphael CHAI Zhengyu",
        
    
    
    # 可以继续添加更多工号...
}

# 日志配置
LOG_FILE = os.path.join(SCRIPT_DIR, "eoms_alert_monitor.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 请求头（使用 SESSION）
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Cookie": f"SESSION={SESSION}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}


def convert_staff_id_to_name(staff_ids: str) -> str:
    """
    将工号转换为带姓名的格式
    如果工号是Mark(P7823)的，则过滤掉不显示
    
    Args:
        staff_ids: 工号字符串，可能包含多个工号，用逗号分隔
    
    Returns:
        转换后的字符串
    """
    if not staff_ids:
        return ""  # 返回空字符串，这样显示就是"待处理人："
    
    # 分割多个工号
    ids = [id.strip() for id in staff_ids.split(",")]
    result = []
    
    for staff_id in ids:
        staff_id_upper = staff_id.upper()
        
        # 跳过Mark的工号
        if staff_id_upper == "P7823":  # Mark的工号
            continue  # 跳过这个工号，不显示
        
        # 其他工号正常处理
        if staff_id_upper in STAFF_ID_MAP:
            result.append(f"{staff_id} {STAFF_ID_MAP[staff_id_upper]}")
        else:
            if staff_id in STAFF_ID_MAP:
                result.append(f"{staff_id} {STAFF_ID_MAP[staff_id]}")
            else:
                result.append(staff_id)
    
    return ", ".join(result)


class EOmsAlertMonitor:
    """EOMS 工单监控告警器"""
    
    # NCOA SESSION 过期最大重试次数
    MAX_NCOA_RETRY = 3
    
    def __init__(self):
        self.eoms_base_url = "https://eoms2.cmhktry.com/x5"
        self.ncoa_base_url = "10.0.17.170"
        self.ncoa_headers = HEADERS  # NCOA 请求头
        self.eoms_headers = {}       # EOMS 请求头（通过登录获取）
        self.eoms_authenticated = False
        
        # NCOA SESSION 过期重试计数器
        self.ncoa_retry_count = 0
        self.script_stopped = False  # 脚本是否已停止
    
    async def _login_and_get_eoms_headers(self, use_cache: bool = True) -> bool:
        """
        登录 EOMS 并获取请求头（无头模式，自动填写账号密码）
        返回是否成功
        """
        async with async_playwright() as p:
            # 无头模式启动浏览器
            browser = await p.chromium.launch(headless=True)
            
            # 尝试使用缓存
            if use_cache and os.path.exists(EOMS_STORAGE_STATE_FILE):
                logging.info(f"📂 发现 EOMS 缓存登录状态")
                print(f"📂 发现 EOMS 缓存登录状态: {EOMS_STORAGE_STATE_FILE}")
                
                context = await browser.new_context(
                    storage_state=EOMS_STORAGE_STATE_FILE,
                    ignore_https_errors=True,
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()
                
                try:
                    await page.goto(f"{self.eoms_base_url}/main/home", wait_until="networkidle", timeout=30000)
                    
                    # 检查是否需要重新登录
                    if "ncas.cmhktry.com" not in page.url:
                        logging.info("✅ EOMS 缓存有效，无需重新登录")
                        print("✅ EOMS 缓存有效，无需重新登录")
                        
                        # 获取 cookies
                        cookies = await context.cookies()
                        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                        self.eoms_headers = {
                            "Accept": "application/json, text/plain, */*",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "Cookie": cookie_str,
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        }
                        
                        # 更新缓存
                        await context.storage_state(path=EOMS_STORAGE_STATE_FILE)
                        await browser.close()
                        
                        self.eoms_authenticated = True
                        return True
                    else:
                        logging.warning("⚠️ EOMS 缓存已过期，需要重新登录")
                        print("⚠️ EOMS 缓存已过期，需要重新登录")
                        await context.close()
                except Exception as e:
                    logging.error(f"使用缓存登录失败: {e}")
                    print(f"⚠️ 使用缓存登录失败: {e}")
                    await context.close()
            
            await browser.close()
            
            # ========== 无头模式自动登录 ==========
            print("\n🔐 正在无头模式自动登录 EOMS...")
            logging.info("正在无头模式自动登录 EOMS...")
            
            # 检查账号密码是否配置
            if EOMS_USERNAME == "your_username" or EOMS_PASSWORD == "your_password":
                logging.error("请配置 EOMS_USERNAME 和 EOMS_PASSWORD!")
                print("❌ 请在文件顶部配置 EOMS_USERNAME 和 EOMS_PASSWORD!")
                return False
            
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                ignore_https_errors=True,
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            
            try:
                # 访问 EOMS，会跳转到 CAS 登录页
                await page.goto(self.eoms_base_url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(2)
                
                current_url = page.url
                logging.info(f"当前 URL: {current_url}")
                print(f"📍 当前 URL: {current_url[:60]}...")
                
                # 检查是否在 CAS 登录页
                if "ncas.cmhktry.com" in current_url or "cas" in current_url.lower():
                    logging.info("检测到 CAS 登录页，正在自动填写账号密码...")
                    print("🔑 检测到 CAS 登录页，正在自动填写账号密码...")
                    
                    # 等待登录表单加载
                    await page.wait_for_selector('input[name="username"]', timeout=10000)
                    
                    # 填写账号
                    await page.fill('input[name="username"]', EOMS_USERNAME)
                    logging.info(f"已填写账号: {EOMS_USERNAME}")
                    print(f"✅ 已填写账号: {EOMS_USERNAME}")
                    
                    # 填写密码
                    await page.fill('input[name="password"]', EOMS_PASSWORD)
                    logging.info("已填写密码")
                    print("✅ 已填写密码")
                    
                    await asyncio.sleep(1)
                    
                    # 点击登录按钮
                    # 尝试多种选择器
                    login_selectors = [
                        'button[type="submit"]',
                        'input[type="submit"]',
                        'button:has-text("登录")',
                        'button:has-text("Login")',
                        '.btn-submit',
                        '#submit',
                    ]
                    
                    clicked = False
                    for selector in login_selectors:
                        try:
                            if await page.locator(selector).count() > 0:
                                await page.click(selector)
                                clicked = True
                                logging.info(f"点击了登录按钮: {selector}")
                                print(f"✅ 点击了登录按钮")
                                break
                        except:
                            continue
                    
                    if not clicked:
                        # 尝试按 Enter 键
                        await page.press('input[name="password"]', 'Enter')
                        logging.info("按下 Enter 键提交登录")
                        print("✅ 按下 Enter 键提交登录")
                    
                    # 等待跳转到 EOMS
                    logging.info("等待登录完成...")
                    print("⏳ 等待登录完成...")
                    
                    await page.wait_for_url(
                        lambda url: "eoms2.cmhktry.com" in url and "ncas" not in url,
                        timeout=60000
                    )
                    
                    # 等待页面完全加载
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)
                
                # 确保在 EOMS 首页
                current_url = page.url
                if "eoms2.cmhktry.com" in current_url:
                    logging.info("✅ EOMS 自动登录成功!")
                    print("✅ EOMS 自动登录成功!")
                    
                    # 如果不在首页，跳转到首页
                    if "/main/home" not in current_url:
                        await page.goto(f"{self.eoms_base_url}/main/home", wait_until="networkidle")
                        await asyncio.sleep(2)
                    
                    # 获取 cookies
                    cookies = await context.cookies()
                    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                    self.eoms_headers = {
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                        "Cookie": cookie_str,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    }
                    
                    # 保存缓存
                    await context.storage_state(path=EOMS_STORAGE_STATE_FILE)
                    logging.info(f"💾 已保存 EOMS 登录状态")
                    print(f"💾 已保存 EOMS 登录状态到: {EOMS_STORAGE_STATE_FILE}")
                    
                    await browser.close()
                    self.eoms_authenticated = True
                    return True
                else:
                    logging.error(f"登录后未跳转到 EOMS，当前 URL: {current_url}")
                    print(f"❌ 登录后未跳转到 EOMS，当前 URL: {current_url}")
                    await browser.close()
                    return False
                
            except Exception as e:
                logging.error(f"EOMS 自动登录失败: {e}")
                print(f"❌ EOMS 自动登录失败: {e}")
                await browser.close()
                return False
    
    def ensure_eoms_authenticated(self, force_relogin: bool = False) -> bool:
        """
        确保 EOMS 已认证
        
        Args:
            force_relogin: 是否强制重新登录（忽略缓存）
        """
        if force_relogin:
            self.eoms_authenticated = False
            # 删除缓存文件
            if os.path.exists(EOMS_STORAGE_STATE_FILE):
                os.remove(EOMS_STORAGE_STATE_FILE)
                logging.info("已删除过期的 EOMS 缓存")
                print("🗑️ 已删除过期的 EOMS 缓存")
        
        if self.eoms_authenticated:
            return True
        
        # 运行异步登录
        return asyncio.run(self._login_and_get_eoms_headers())
    
    def _is_cas_login_page(self, response_text: str) -> bool:
        """
        检查响应是否是 CAS 登录页面
        """
        cas_indicators = [
            "ncas.cmhktry.com",
            "cas/login",
            "j_spring_cas_security_check",
            "id=\"loginForm\"",
            "name=\"password\"",
            "<title>统一认证平台</title>",
            "Central Authentication Service"
        ]
        return any(indicator in response_text for indicator in cas_indicators)
    
    def get_ticket_info_from_form_link(self, form_link_pc: str, retry_count: int = 0) -> tuple:
        """
        从工单链接获取工单信息
        
        原始链接格式: https://eoms2.cmhktry.com/x5/flow/try/tryTaskApprove?id=10000244710045
        需要请求的是: https://eoms2.cmhktry.com/x5/flow/task/taskDetail?taskId=10000244710045
        
        Args:
            form_link_pc: 原始工单链接
            retry_count: 重试次数（内部使用）
        
        返回: (inst_id, issuedto)
        """
        MAX_RETRY = 1  # 最多重试1次（检测到登录页后重新登录再试一次）
        
        # 确保 EOMS 已认证
        if not self.ensure_eoms_authenticated():
            logging.error("EOMS 认证失败，无法获取工单信息")
            print("❌ EOMS 认证失败")
            return "", ""
        
        try:
            # 从原始链接提取 taskId（即 id 参数）
            # 原始链接: https://eoms2.cmhktry.com/x5/flow/try/tryTaskApprove?id=10000244710045
            task_id = ""
            if "id=" in form_link_pc:
                task_id = form_link_pc.split("id=")[-1].split("&")[0]
            
            if not task_id:
                logging.error(f"无法从链接提取 taskId: {form_link_pc}")
                print(f"❌ 无法从链接提取 taskId")
                return "", ""
            
            # 构造 taskDetail 请求 URL
            detail_url = f"{self.eoms_base_url}/flow/task/taskDetail?taskId={task_id}"
            
            logging.info(f"原始链接: {form_link_pc}")
            logging.info(f"taskId: {task_id}")
            logging.info(f"请求详情: {detail_url}")
            print(f"🔍 taskId: {task_id}")
            print(f"🔍 请求详情: {detail_url}")
            
            # 使用 EOMS headers（包含认证 cookie）
            response = requests.get(detail_url, headers=self.eoms_headers, verify=False, allow_redirects=True)
            logging.info(f"响应状态码: {response.status_code}")
            logging.info(f"最终 URL: {response.url}")
            print(f"📥 响应状态码: {response.status_code}")
            
            if response.status_code != 200:
                logging.error(f"获取工单信息失败: {response.status_code}")
                return "", ""
            
            # 检查是否跳转到了 CAS 登录页面
            if self._is_cas_login_page(response.text) or "ncas.cmhktry.com" in response.url:
                logging.warning("⚠️ 检测到 CAS 登录页面，EOMS 认证已过期")
                print("⚠️ 检测到 CAS 登录页面，EOMS 认证已过期")
                
                if retry_count < MAX_RETRY:
                    logging.info("正在重新登录 EOMS...")
                    print("🔄 正在重新登录 EOMS...")
                    
                    # 强制重新登录（清除缓存）
                    if self.ensure_eoms_authenticated(force_relogin=True):
                        logging.info("EOMS 重新登录成功，重试请求")
                        print("✅ EOMS 重新登录成功，重试请求")
                        return self.get_ticket_info_from_form_link(form_link_pc, retry_count + 1)
                    else:
                        logging.error("EOMS 重新登录失败")
                        print("❌ EOMS 重新登录失败")
                        return "", ""
                else:
                    logging.error("已达到最大重试次数，仍无法获取工单信息")
                    print("❌ 已达到最大重试次数")
                    return "", ""
            
            # 保存响应内容供调试
            debug_file = os.path.join(SCRIPT_DIR, "debug_response.txt")
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(f"原始链接: {form_link_pc}\n")
                f.write(f"taskId: {task_id}\n")
                f.write(f"请求URL: {detail_url}\n")
                f.write(f"最终URL: {response.url}\n")
                f.write(f"Status: {response.status_code}\n")
                f.write(f"Headers: {dict(response.headers)}\n")
                f.write(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}\n")
                f.write(f"\n--- Response Body ---\n")
                f.write(response.text[:10000])  # 保存前10000字符
            logging.info(f"已保存调试响应到: {debug_file}")
            print(f"📝 已保存调试响应到: {debug_file}")
            
            # 清理响应文本中的控制字符（处理 Windows 换行符等）
            response_text = response.text
            response_text_clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response_text)
            
            try:
                # 优先使用清理后的文本解析 JSON
                data_json = json.loads(response_text_clean)
                logging.info(f"获取到工单 JSON 响应")
                print(f"✅ 响应是 JSON 格式")
                
                # 打印顶层键
                logging.info(f"JSON 顶层键: {list(data_json.keys())}")
                print(f"📊 JSON 顶层键: {list(data_json.keys())}")
                
                # 提取 instId
                inst_id = ""
                if "data" in data_json and "instId" in data_json["data"]:
                    inst_id = str(data_json["data"]["instId"])
                    logging.info(f"提取到 instId: {inst_id}")
                    print(f"✅ 提取到 instId: {inst_id}")
                else:
                    logging.warning(f"未找到 data.instId，data 内容: {list(data_json.get('data', {}).keys()) if 'data' in data_json else 'data 不存在'}")
                    print(f"⚠️ 未找到 data.instId")
                
                # 提取 Issuedto（待处理人工号）
                issuedto = ""
                if "data" in data_json:
                    # 尝试从 SecurityIncident2 中获取
                    if "SecurityIncident2" in data_json["data"]:
                        issuedto = data_json["data"]["SecurityIncident2"].get("Issuedto", "")
                        if issuedto:
                            print(f"✅ 从 SecurityIncident2 提取到 Issuedto: {issuedto}")
                    # 也可能在其他位置，遍历查找
                    if not issuedto:
                        for key, value in data_json["data"].items():
                            if isinstance(value, dict) and "Issuedto" in value:
                                issuedto = value["Issuedto"]
                                print(f"✅ 从 {key} 提取到 Issuedto: {issuedto}")
                                break
                    
                    if issuedto:
                        logging.info(f"提取到 Issuedto: {issuedto}")
                    else:
                        logging.warning(f"未找到 Issuedto")
                        print(f"⚠️ 未找到 Issuedto")
                
                return inst_id, issuedto
                
            except json.JSONDecodeError as e:
                # 如果不是 JSON，尝试从 HTML 解析
                logging.info(f"响应不是 JSON: {e}")
                print(f"⚠️ 响应不是 JSON，尝试从 HTML 解析")
                
                # 使用清理后的文本
                html = response_text_clean
                
                inst_id = ""
                issuedto = ""
                
                # 匹配 流程编号:10000244688687
                pattern = r'流程编号[：:](\d+)'
                match = re.search(pattern, html)
                if match:
                    inst_id = match.group(1)
                    print(f"✅ 从 HTML 提取到 instId: {inst_id}")
                else:
                    print(f"⚠️ 从 HTML 也未能提取到 instId")
                
                # 尝试从 HTML 中提取 Issuedto
                # 可能的格式: "Issuedto":"P7823" 或 Issuedto 在某个 JSON 片段中
                issuedto_pattern = r'"Issuedto"\s*:\s*"([^"]*)"'
                issuedto_match = re.search(issuedto_pattern, html)
                if issuedto_match:
                    issuedto = issuedto_match.group(1)
                    print(f"✅ 从 HTML 提取到 Issuedto: {issuedto}")
                else:
                    print(f"⚠️ 从 HTML 也未能提取到 Issuedto")
                
                return inst_id, issuedto
                
        except Exception as e:
            logging.error(f"获取工单信息出错: {e}")
            print(f"❌ 获取工单信息出错: {e}")
            return "", ""
    
    def _is_connection_error(self, error: Exception) -> bool:
        """
        检查是否是连接超时/网络错误
        这类错误不需要发送告警，直接重试即可
        """
        error_str = str(error).lower()
        connection_error_keywords = [
            "connectiontimeouterror",
            "connecttimeouterror",
            "connection to",
            "timed out",
            "timeout",
            "max retries exceeded",
            "connectionerror",
            "connection refused",
            "connection reset",
            "network is unreachable",
        ]
        return any(keyword in error_str for keyword in connection_error_keywords)
    
    def get_data_new(self):
        """
        获取新工单（最近5分钟内）
        """
        # 检查脚本是否已停止
        if self.script_stopped:
            logging.info("脚本已停止，不再执行 get_data_new")
            return
        
        today = datetime.now()
        formatted_date = today.strftime('%Y-%m-%d')
        now = datetime.now()
        five_minutes_ago = now - timedelta(minutes=5)
        all_url = f"{self.ncoa_base_url}/gateway/todo/todo/todo/list?pageNum=1&pageSize=10&title=&sender=&beginTime={formatted_date}&endTime={formatted_date}%2023%3A59%3A59&sort=0&drafter=&timeoutPriority=true&uuid="
        
        try:
            response = requests.get(all_url, headers=self.ncoa_headers, verify=False, timeout=30)
            data_json = response.json()
        except json.JSONDecodeError as e:
            logging.error(f"get_data_new JSON 解析失败: {e}")
            logging.info(f"Response text: {response.text[:500]}")
            
            # 检查是否返回了 HTML 页面（SESSION 过期的标志）
            if "<html" in response.text.lower() or "<!doctype" in response.text.lower():
                logging.warning("返回了 HTML 页面，NCOA SESSION 可能过期")
                # 按 SESSION 过期处理
                self.ncoa_retry_count += 1
                print(f"⚠️ NCOA SESSION 可能过期（返回 HTML），重试次数: {self.ncoa_retry_count}/{self.MAX_NCOA_RETRY}")
                
                if self.ncoa_retry_count >= self.MAX_NCOA_RETRY:
                    logging.error(f"NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次，停止脚本执行")
                    print(f"\n❌ NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次")
                    print("=" * 60)
                    print("请手动更新 NCOA SESSION 后重新启动脚本")
                    print(f"当前 SESSION: {SESSION[:20]}...")
                    print("获取方式: 浏览器登录 NCOA -> F12 -> Application -> Cookies -> SESSION")
                    print("=" * 60)
                    self.send_session_expired_alert()
                    self.script_stopped = True
                    return
                
                threading.Timer(60, self.get_data_new).start()
                return
            
            # 其他 JSON 解析错误才发送告警
            self.send_alert_EOMS("程序报错了", str(e), "None", "", "")
            threading.Timer(300, self.get_data_new).start()  # 5分钟后重试
            return
        except (ConnectionError, Timeout, RequestException) as e:
            # 连接超时/网络错误，不发送告警，直接重试
            logging.warning(f"get_data_new 网络连接错误（不发送告警，60秒后重试）: {e}")
            print(f"⚠️ 网络连接错误，60秒后重试: {str(e)[:100]}...")
            threading.Timer(60, self.get_data_new).start()  # 60秒后重试
            return
        except Exception as e:
            # 检查是否是连接相关错误
            if self._is_connection_error(e):
                logging.warning(f"get_data_new 连接错误（不发送告警，60秒后重试）: {e}")
                print(f"⚠️ 连接错误，60秒后重试: {str(e)[:100]}...")
                threading.Timer(60, self.get_data_new).start()  # 60秒后重试
                return
            
            logging.error(f"get_data_new 请求失败: {e}")
            self.send_alert_EOMS("程序报错了", str(e), "None", "", "")
            threading.Timer(300, self.get_data_new).start()  # 5分钟后重试
            return
        
        if "rows" in data_json:
            for item in data_json["rows"]:
                receive_time = datetime.strptime(item['receiveTime'], '%Y-%m-%d %H:%M:%S')
                if receive_time >= five_minutes_ago:
                    # 从访问链接获取工单信息（instId 和 Issuedto）
                    inst_id, issuedto = self.get_ticket_info_from_form_link(item["formLinkPc"])
                    if inst_id:
                        logging.info(f"获取到 inst_id: {inst_id}")
                    else:
                        logging.warning(f"未能获取 inst_id，但仍会发送通知")
                    
                    if issuedto:
                        logging.info(f"获取到待处理人工号: {issuedto}")
                    else:
                        logging.warning(f"未能获取待处理人工号")
                    
                    # 无论是否获取到信息，都发送通知
                    if "Security Incident" in item["title"]:
                        self.send_alert_EOMS(item["title"], item["formLinkPc"], item["receiveTime"], inst_id, issuedto)
                        logging.info(f"发送了 EOMS 告警: {item['title']}")
                    # ITSR 相关暂时注释掉
                    # else:
                    #     self.send_alert_ITSR(item["title"], item["formLinkPc"], item["receiveTime"])
                    #     logging.info(f"发送了 ITSR 告警: {item['title']}")
            
            logging.info(f"now值为: {now}; five_minutes_ago值为: {five_minutes_ago}")
            # 存活探测已关闭
            # self.send_test_msg(f"存活探测：执行了一次, 执行时间为：{now}")
            logging.info("执行了一次 get_data_new")
            
            # 成功获取数据，重置 NCOA 重试计数器
            self.ncoa_retry_count = 0
        else:
            # NCOA SESSION 过期或返回数据异常
            # 注意：NCOA SESSION 只能人工更新，无法自动获取
            self.ncoa_retry_count += 1
            
            logging.warning(f"get_data_new 返回数据异常（NCOA SESSION 可能过期），重试次数: {self.ncoa_retry_count}/{self.MAX_NCOA_RETRY}")
            print(f"⚠️ NCOA SESSION 可能过期，重试次数: {self.ncoa_retry_count}/{self.MAX_NCOA_RETRY}")
            
            if "code" in data_json:
                logging.warning(f"错误 code: {data_json['code']}")
            
            # 检查是否达到最大重试次数
            if self.ncoa_retry_count >= self.MAX_NCOA_RETRY:
                logging.error(f"NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次，停止脚本执行")
                print(f"\n❌ NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次")
                print("=" * 60)
                print("请手动更新 NCOA SESSION 后重新启动脚本")
                print(f"当前 SESSION: {SESSION[:20]}...")
                print("获取方式: 浏览器登录 NCOA -> F12 -> Application -> Cookies -> SESSION")
                print("=" * 60)
                # 发送告警到飞书
                self.send_session_expired_alert()
                self.script_stopped = True
                # 不再设置定时器，脚本停止
                return
            
            # 60秒后重试
            threading.Timer(60, self.get_data_new).start()
            return
        
        threading.Timer(300, self.get_data_new).start()  # 每5分钟检测一次
    
    def get_data_old(self):
        """
        获取旧的未处理工单（超过30分钟）
        """
        # 检查脚本是否已停止
        if self.script_stopped:
            logging.info("脚本已停止，不再执行 get_data_old")
            return
        
        now = datetime.now()
        thirty_minutes_ago = now - timedelta(minutes=30)
        
        eoms_url = f"{self.ncoa_base_url}/gateway/todo/todo/todo/list?pageNum=1&pageSize=10&title=&sender=&beginTime=&endTime=&sort=0&drafter=&categoryId=202401250048649563&timeoutPriority=true&curStep="
        
        try:
            response = requests.get(eoms_url, headers=self.ncoa_headers, verify=False, timeout=30)
            data_json = response.json()
        except json.JSONDecodeError as e:
            logging.error(f"get_data_old JSON 解析失败: {e}")
            logging.info(f"Response text: {response.text[:500]}")
            
            # 检查是否返回了 HTML 页面（SESSION 过期的标志）
            if "<html" in response.text.lower() or "<!doctype" in response.text.lower():
                logging.warning("返回了 HTML 页面，NCOA SESSION 可能过期")
                # 按 SESSION 过期处理
                self.ncoa_retry_count += 1
                print(f"⚠️ NCOA SESSION 可能过期（返回 HTML），重试次数: {self.ncoa_retry_count}/{self.MAX_NCOA_RETRY}")
                
                if self.ncoa_retry_count >= self.MAX_NCOA_RETRY:
                    logging.error(f"NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次，停止脚本执行")
                    print(f"\n❌ NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次")
                    print("=" * 60)
                    print("请手动更新 NCOA SESSION 后重新启动脚本")
                    print(f"当前 SESSION: {SESSION[:20]}...")
                    print("获取方式: 浏览器登录 NCOA -> F12 -> Application -> Cookies -> SESSION")
                    print("=" * 60)
                    self.send_session_expired_alert()
                    self.script_stopped = True
                    return
                
                threading.Timer(60, self.get_data_old).start()
                return
            
            threading.Timer(900, self.get_data_old).start()  # 15分钟后重试
            return
        except (ConnectionError, Timeout, RequestException) as e:
            # 连接超时/网络错误，不发送告警，直接重试
            logging.warning(f"get_data_old 网络连接错误（不发送告警，60秒后重试）: {e}")
            print(f"⚠️ 网络连接错误，60秒后重试: {str(e)[:100]}...")
            threading.Timer(60, self.get_data_old).start()  # 60秒后重试
            return
        except Exception as e:
            # 检查是否是连接相关错误
            if self._is_connection_error(e):
                logging.warning(f"get_data_old 连接错误（不发送告警，60秒后重试）: {e}")
                print(f"⚠️ 连接错误，60秒后重试: {str(e)[:100]}...")
                threading.Timer(60, self.get_data_old).start()  # 60秒后重试
                return
            
            logging.error(f"get_data_old 请求失败: {e}")
            threading.Timer(900, self.get_data_old).start()  # 15分钟后重试
            return
        
        if "rows" in data_json:
            for item in data_json["rows"]:
                receive_time = datetime.strptime(item['receiveTime'], '%Y-%m-%d %H:%M:%S')
                if receive_time < thirty_minutes_ago:
                    if "10000121600209" not in item["formLinkPc"]:
                        time_diff = datetime.now() - receive_time
                        days = time_diff.days
                        hours, remainder = divmod(time_diff.seconds, 3600)
                        minutes = remainder // 60
                        
                        # 从访问链接获取工单信息（instId 和 Issuedto）
                        inst_id, issuedto = self.get_ticket_info_from_form_link(item["formLinkPc"])
                        if inst_id:
                            logging.info(f"获取到 inst_id: {inst_id}")
                        else:
                            logging.warning(f"未能获取 inst_id，但仍会发送通知")
                        
                        if issuedto:
                            logging.info(f"获取到待处理人工号: {issuedto}")
                        else:
                            logging.warning(f"未能获取待处理人工号")
                        
                        # 无论是否获取到信息，都发送通知
                        self.send_alert_EOMS_old(
                            item["title"],
                            item["formLinkPc"],
                            item["receiveTime"],
                            f"{days} days {hours} hours {minutes} minutes",
                            inst_id,
                            issuedto
                        )
                        logging.info(f"发送了旧工单告警: {item['title']}")
            
            logging.info("执行了一次 get_data_old")
            
            # 成功获取数据，重置 NCOA 重试计数器
            self.ncoa_retry_count = 0
        else:
            # NCOA SESSION 过期或返回数据异常
            # 注意：NCOA SESSION 只能人工更新，无法自动获取
            self.ncoa_retry_count += 1
            
            logging.warning(f"get_data_old 返回数据异常（NCOA SESSION 可能过期），重试次数: {self.ncoa_retry_count}/{self.MAX_NCOA_RETRY}")
            print(f"⚠️ NCOA SESSION 可能过期，重试次数: {self.ncoa_retry_count}/{self.MAX_NCOA_RETRY}")
            
            if "code" in data_json:
                logging.warning(f"错误 code: {data_json['code']}")
            
            # 检查是否达到最大重试次数
            if self.ncoa_retry_count >= self.MAX_NCOA_RETRY:
                logging.error(f"NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次，停止脚本执行")
                print(f"\n❌ NCOA SESSION 过期，已重试 {self.MAX_NCOA_RETRY} 次")
                print("=" * 60)
                print("请手动更新 NCOA SESSION 后重新启动脚本")
                print(f"当前 SESSION: {SESSION[:20]}...")
                print("获取方式: 浏览器登录 NCOA -> F12 -> Application -> Cookies -> SESSION")
                print("=" * 60)
                # 发送告警到飞书
                self.send_session_expired_alert()
                self.script_stopped = True
                # 不再设置定时器，脚本停止
                return
            
            # 60秒后重试
            threading.Timer(60, self.get_data_old).start()
            return
        
        threading.Timer(900, self.get_data_old).start()  # 每15分钟检测一次
    
    # ITSR 相关暂时注释掉
    # def send_alert_ITSR(self, title: str, url: str, receive_time: str):
    #     """发送 ITSR 工单告警"""
    #     payload = {
    #         "msg_type": "text",
    #         "content": {
    #             "text": f"有新的ITSR工单了\n标题名称：{title}\n访问链接：{url}\n接收时间：{receive_time}"
    #         }
    #     }
    #     requests.post(FEISHU_WEBHOOK_URL, headers={'Content-Type': 'application/json'}, json=payload)
    
    def send_alert_EOMS(self, title: str, url: str, receive_time: str, inst_id: str, issuedto: str):
        """发送安全 EOMS 工单告警（包含工单号和待处理人工号）"""
        inst_id_display = inst_id if inst_id else "未获取到"
        # 将工号转换为带姓名的格式
        issuedto_display = convert_staff_id_to_name(issuedto) if issuedto else "未获取到"
        
        text = (
            f"有新的安全EOMS工单了\n"
            f"\n"
            f"标题名称：{title}\n"
            f"工单号：{inst_id_display}\n"
            f"访问链接：{url}\n"
            f"待处理人：{issuedto_display}\n"
            f"接收时间：{receive_time}"
        )
        
        payload = {
            "msg_type": "text",
            "content": {"text": text}
        }
        requests.post(FEISHU_WEBHOOK_URL, headers={'Content-Type': 'application/json'}, json=payload)
    
    def send_alert_EOMS_old(self, title: str, url: str, receive_time: str, time_passed: str, inst_id: str, issuedto: str):
        """发送旧的未处理 EOMS 工单告警"""
        inst_id_display = inst_id if inst_id else "未获取到"
        # 将工号转换为带姓名的格式
        issuedto_display = convert_staff_id_to_name(issuedto) if issuedto else "未获取到"
        
        text = (
            f"有旧的安全EOMS工单未处理\n"
            f"\n"
            f"标题名称：{title}\n"
            f"工单号：{inst_id_display}\n"
            f"访问链接为：{url}\n"
            f"待处理人：{issuedto_display}\n"
            f"接收时间：{receive_time}\n"
            f"距离接收到的时间已过  {time_passed}"
        )
        
        payload = {
            "msg_type": "text",
            "content": {"text": text}
        }
        requests.post(FEISHU_WEBHOOK_URL, headers={'Content-Type': 'application/json'}, json=payload)
    
    def send_session_expired_alert(self):
        """发送 NCOA SESSION 过期告警"""
        text = (
            f"⚠️ NCOA SESSION 过期，需更新！\n"
            f"\n"
            f"EOMS 告警监控脚本已停止运行\n"
            f"请手动更新 SESSION 后重新启动脚本\n"
            f"\n"
            f"获取方式:\n"
            f"浏览器登录 NCOA -> F12 -> Application -> Cookies -> SESSION"
        )
        
        payload = {
            "msg_type": "text",
            "content": {"text": text}
        }
        try:
            requests.post(FEISHU_WEBHOOK_URL, headers={'Content-Type': 'application/json'}, json=payload)
            logging.info("已发送 SESSION 过期告警到飞书")
            print("📤 已发送 SESSION 过期告警到飞书")
        except Exception as e:
            logging.error(f"发送 SESSION 过期告警失败: {e}")
    
    def send_test_msg(self, msg: str):
        """发送测试/存活探测消息"""
        payload = {
            "msg_type": "text",
            "content": {"text": msg}
        }
        requests.post(FEISHU_WEBHOOK_URL, headers={'Content-Type': 'application/json'}, json=payload)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("EOMS 工单监控告警脚本（无头模式自动登录）")
    print("=" * 60)
    print(f"EOMS 账号: {EOMS_USERNAME}")
    print(f"NCOA SESSION: {SESSION[:20]}...")
    print(f"EOMS 缓存: {EOMS_STORAGE_STATE_FILE}")
    print(f"日志文件: {LOG_FILE}")
    print("=" * 60)
    
    # 检查账号密码配置
    if EOMS_USERNAME == "your_username" or EOMS_PASSWORD == "your_password":
        print("\n⚠️ 请在文件顶部配置 EOMS_USERNAME 和 EOMS_PASSWORD!")
        print("  找到以下行并替换为您的实际凭证:")
        print('    EOMS_USERNAME = "your_username"')
        print('    EOMS_PASSWORD = "your_password"')
        return
    
    monitor = EOmsAlertMonitor()
    
    # 预先进行 EOMS 认证
    print("\n🔐 正在初始化 EOMS 认证...")
    if monitor.ensure_eoms_authenticated():
        print("✅ EOMS 认证成功")
    else:
        print("⚠️ EOMS 认证失败，工单详情可能无法获取")
    
    print("\n📡 开始监控新工单（每5分钟）")
    print("📡 开始监控旧工单（每15分钟）")
    print("📡 程序启动时立即执行一次检测...")
    
    monitor.get_data_new()
    monitor.get_data_old()
    
    print("\n✅ 监控已启动，按 Ctrl+C 停止")
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n⏹️ 监控已停止")


if __name__ == "__main__":
    main()
