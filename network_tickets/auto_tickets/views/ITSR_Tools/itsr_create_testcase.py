#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试开单脚本 - 直接执行即可
"""

import sys
import os
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# 确保能 import itsr_create（同目录）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from itsr_create import (
    create_ticket_session,
    submit_credentials,
    submit_sms_code,
    wait_create_result,
)

# ============================================================================
# 1. 创建会话
# ============================================================================
session_id = create_ticket_session(
    title="测试工单",
    description="这是一个测试需求",
    product_line_id="1254515022491552748",   # ISM (網絡支撐)
    urgency="DI",
    requirement_type="FEIKAIFAXUQIU",
    attachment_files=["test.xlsx"],           # attachments/test.xlsx
)
print(f"会话已创建: {session_id}")

# ============================================================================
# 2. 输入账号密码
# ============================================================================
username = input("用户名: ").strip()
password = input("密码: ").strip()

print("正在登录...")
success, msg = submit_credentials(session_id, username, password)

if not success:
    print(f"登录失败: {msg}")
    sys.exit(1)

# ============================================================================
# 3. 根据是否需要验证码处理
# ============================================================================
if msg == "NO_SMS_REQUIRED":
    print("无需验证码，正在创建工单...")
    result = wait_create_result(session_id)
else:
    print("需要验证码，请查看手机短信")
    sms_code = input("验证码 (6位): ").strip()
    print("正在创建工单...")
    result = submit_sms_code(session_id, sms_code)

# ============================================================================
# 4. 输出结果
# ============================================================================
if result.success:
    print(f"\n工单创建成功!")
    print(f"  工单号:   {result.bill_code}")
    print(f"  Case ID:  {result.case_id}")
    print(f"  标题:     {result.subject}")
else:
    print(f"\n工单创建失败: {result.error}")
    sys.exit(1)
