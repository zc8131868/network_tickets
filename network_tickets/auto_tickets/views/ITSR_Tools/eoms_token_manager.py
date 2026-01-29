#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EOMS Token 管理模块
- 负责获取和刷新 Token
- 保存 Token 到 Redis（以 app_id 为 key）
- 每 4 小时自动刷新一次 Token
- 可作为独立进程运行，也可被其他模块导入使用
"""

import time
import random
import string
import logging
import threading
from datetime import datetime
from typing import Optional

import requests
import urllib3
import redis

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================
# API 凭证配置（请替换为您的实际凭证）
# ============================================================
APP_ID = "siffdj4u56nvdm5jtw"
APP_SECRET = "b756f501776429e8178b16a91aee1e1d89da5efd"

# ============================================================
# Redis 配置
# ============================================================
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None  # 如果有密码请填写

# ============================================================
# API 配置
# ============================================================
API_BASE_URL = "https://bcocesb.hk.chinamobile.com/bcoc"
TOKEN_ENDPOINT = "/refreshToken"

# Token 刷新间隔（秒）- 4小时
TOKEN_REFRESH_INTERVAL = 4 * 60 * 60  # 14400 秒

# 请求标识配置
TENANT_ID = "CMHK"
CHANNEL = "BH_cmhk_001"
PATH = "C0001"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TokenManager:
    """
    Token 管理器
    
    负责：
    - 获取和刷新 Token
    - 保存 Token 到 Redis（以 app_id 为 key，token 为 value，expiresIn 为过期时间）
    - 每 4 小时自动刷新一次 Token
    """
    
    def __init__(
        self,
        app_id: str = APP_ID,
        app_secret: str = APP_SECRET,
        redis_host: str = REDIS_HOST,
        redis_port: int = REDIS_PORT,
        redis_db: int = REDIS_DB,
        redis_password: str = REDIS_PASSWORD,
        refresh_interval: int = TOKEN_REFRESH_INTERVAL,
    ):
        """
        初始化 Token 管理器
        
        Args:
            app_id: 应用唯一凭证
            app_secret: 应用唯一凭证密钥
            redis_host: Redis 主机地址
            redis_port: Redis 端口
            redis_db: Redis 数据库编号
            redis_password: Redis 密码
            refresh_interval: Token 刷新间隔（秒），默认 4 小时
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.refresh_interval = refresh_interval
        
        # Redis 连接
        self.redis_client = None
        self._init_redis(redis_host, redis_port, redis_db, redis_password)
        
        # 自动刷新线程
        self._refresh_timer = None
        self._running = False
    
    def _init_redis(self, host: str, port: int, db: int, password: str):
        """初始化 Redis 连接"""
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
            )
            self.redis_client.ping()
            logger.info(f"Redis 连接成功: {host}:{port}")
        except redis.ConnectionError as e:
            logger.error(f"Redis 连接失败: {e}")
            raise Exception(f"Redis 连接失败: {e}")
    
    def _get_redis_key(self) -> str:
        """获取 Redis 缓存的 key，以 app_id 为 key"""
        return f"eoms_token:{self.app_id}"
    
    def _generate_trace_id(self) -> str:
        """生成 bcoc-trace-id"""
        now_time = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        random_num = ''.join(random.choices(string.digits, k=4))
        trace_id = f"{TENANT_ID}*{CHANNEL}*{now_time}*{PATH}*{random_num}"
        return trace_id
    
    def refresh_token(self) -> str:
        """
        获取新的 Token 并保存到 Redis
        
        Returns:
            新的 access_token
        """
        url = f"{API_BASE_URL}{TOKEN_ENDPOINT}"
        
        payload = {
            "appId": self.app_id,
            "appSecret": self.app_secret,
        }
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "*/*",
        }
        
        logger.info(f"正在刷新 Token...")
        
        try:
            response = requests.post(url, json=payload, headers=headers, verify=False, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("code") != 200 and result.get("code") != "200":
                error_msg = result.get("message", "未知错误")
                raise Exception(f"Token 获取失败: {error_msg}")
            
            access_token = result.get("accessToken")
            expires_in = int(result.get("expiresIn", 7200))
            
            # 保存到 Redis
            redis_key = self._get_redis_key()
            self.redis_client.setex(redis_key, expires_in, access_token)
            
            logger.info(f"✅ Token 刷新成功!")
            logger.info(f"   Token: {access_token[:20]}...")
            logger.info(f"   有效时长: {expires_in} 秒")
            logger.info(f"   Redis Key: {redis_key}")
            
            return access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Token 请求失败: {e}")
            raise Exception(f"Token 请求失败: {e}")
    
    def get_token(self) -> Optional[str]:
        """
        从 Redis 获取当前 Token
        
        Returns:
            当前有效的 Token，如果不存在或已过期返回 None
        """
        if not self.redis_client:
            return None
        
        try:
            redis_key = self._get_redis_key()
            token = self.redis_client.get(redis_key)
            
            if token:
                ttl = self.redis_client.ttl(redis_key)
                logger.debug(f"获取 Token 成功，剩余 TTL: {ttl} 秒")
                return token
            
            return None
            
        except Exception as e:
            logger.error(f"从 Redis 获取 Token 失败: {e}")
            return None
    
    def get_token_ttl(self) -> int:
        """
        获取 Token 剩余有效时间（秒）
        
        Returns:
            剩余 TTL，如果 Token 不存在返回 -1
        """
        if not self.redis_client:
            return -1
        
        try:
            redis_key = self._get_redis_key()
            ttl = self.redis_client.ttl(redis_key)
            return ttl if ttl > 0 else -1
        except Exception as e:
            logger.error(f"获取 Token TTL 失败: {e}")
            return -1
    
    def delete_token(self):
        """删除 Redis 中的 Token"""
        if self.redis_client:
            redis_key = self._get_redis_key()
            self.redis_client.delete(redis_key)
            logger.info(f"已删除 Token: {redis_key}")
    
    def _auto_refresh_loop(self):
        """自动刷新循环"""
        while self._running:
            try:
                self.refresh_token()
                logger.info(f"下次刷新时间: {self.refresh_interval} 秒后 ({self.refresh_interval / 3600:.1f} 小时)")
            except Exception as e:
                logger.error(f"自动刷新 Token 失败: {e}")
                # 失败后 5 分钟重试
                logger.info("5 分钟后重试...")
                time.sleep(300)
                continue
            
            # 等待下次刷新
            time.sleep(self.refresh_interval)
    
    def start_auto_refresh(self):
        """
        启动自动刷新线程
        
        每隔 refresh_interval 秒自动刷新一次 Token
        """
        if self._running:
            logger.warning("自动刷新已在运行")
            return
        
        self._running = True
        
        # 立即刷新一次
        try:
            self.refresh_token()
        except Exception as e:
            logger.error(f"初始刷新 Token 失败: {e}")
        
        # 启动后台刷新线程
        self._refresh_timer = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self._refresh_timer.start()
        
        logger.info(f"✅ 自动刷新已启动，间隔: {self.refresh_interval} 秒 ({self.refresh_interval / 3600:.1f} 小时)")
    
    def stop_auto_refresh(self):
        """停止自动刷新"""
        self._running = False
        if self._refresh_timer:
            self._refresh_timer.join(timeout=1)
            self._refresh_timer = None
        logger.info("自动刷新已停止")


# ============================================================
# 便捷函数：供其他模块导入使用
# ============================================================

_default_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """
    获取默认的 Token 管理器实例（单例模式）
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = TokenManager()
    return _default_manager


def get_token() -> Optional[str]:
    """
    便捷函数：从 Redis 获取当前 Token
    
    用法:
        from eoms_token_manager import get_token
        token = get_token()
    """
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
        redis_key = f"eoms_token:{APP_ID}"
        return redis_client.get(redis_key)
    except Exception as e:
        logger.error(f"获取 Token 失败: {e}")
        return None


def get_token_with_ttl() -> tuple:
    """
    便捷函数：从 Redis 获取当前 Token 及其剩余 TTL
    
    Returns:
        (token, ttl) - Token 和剩余秒数
    """
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
        redis_key = f"eoms_token:{APP_ID}"
        token = redis_client.get(redis_key)
        ttl = redis_client.ttl(redis_key) if token else -1
        return token, ttl
    except Exception as e:
        logger.error(f"获取 Token 失败: {e}")
        return None, -1


def main():
    """
    主函数：作为独立进程运行，持续管理 Token
    """
    print("\n" + "=" * 60)
    print("EOMS Token 管理器")
    print("=" * 60)
    print(f"APP_ID: {APP_ID}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"刷新间隔: {TOKEN_REFRESH_INTERVAL} 秒 ({TOKEN_REFRESH_INTERVAL / 3600:.1f} 小时)")
    print("=" * 60)
    
    # 检查凭证
    if APP_ID == "your_app_id" or APP_SECRET == "your_app_secret":
        print("\n⚠️ 请在文件顶部配置 APP_ID 和 APP_SECRET!")
        return
    
    # 创建 Token 管理器
    try:
        manager = TokenManager()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return
    
    # 启动自动刷新
    manager.start_auto_refresh()
    
    print("\n✅ Token 管理器已启动")
    print("按 Ctrl+C 停止")
    
    # 保持运行
    try:
        while True:
            time.sleep(60)
            # 每分钟打印一次状态
            token = manager.get_token()
            ttl = manager.get_token_ttl()
            if token:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Token 有效，剩余 TTL: {ttl} 秒 ({ttl / 60:.1f} 分钟)")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Token 不存在!")
    except KeyboardInterrupt:
        print("\n⏹️ 正在停止...")
        manager.stop_auto_refresh()
        print("已停止")


if __name__ == "__main__":
    main()

