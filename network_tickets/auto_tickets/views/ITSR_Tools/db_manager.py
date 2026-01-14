#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITSR 数据库管理模块
==================
使用 SQLAlchemy 连接 MySQL 数据库，管理工单数据。

表名: auto_tickets_itsr_network
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from urllib.parse import quote_plus

try:
    from sqlalchemy import create_engine, Column, String, BigInteger, DateTime, text
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    print("请先安装 SQLAlchemy 和 MySQL 驱动: pip install sqlalchemy pymysql")
    raise

# ============================================================================
# 配置
# ============================================================================
@dataclass
class DBConfig:
    """数据库配置"""
    host: str = "172.19.11.14"
    port: int = 3306
    user: str = "chris123"
    password: str = "Cmhk@123"
    database: str = "auto_tickets"  # 数据库名，需要确认
    charset: str = "utf8mb4"
    
    @classmethod
    def from_env(cls) -> 'DBConfig':
        """从环境变量加载配置"""
        return cls(
            host=os.getenv("DB_HOST", cls.host),
            port=int(os.getenv("DB_PORT", cls.port)),
            user=os.getenv("DB_USER", cls.user),
            password=os.getenv("DB_PASSWORD", cls.password),
            database=os.getenv("DB_NAME", cls.database),
        )
    
    @property
    def connection_url(self) -> str:
        """生成 SQLAlchemy 连接 URL（密码已 URL 编码）"""
        encoded_password = quote_plus(self.password)
        return f"mysql+pymysql://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"


# ============================================================================
# 日志配置
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# ORM 模型（匹配实际表结构）
# ============================================================================
Base = declarative_base()


class ITSRNetworkTicket(Base):
    """
    ITSR 网络工单表
    
    实际表结构:
    - id: bigint (PK, AUTO_INCREMENT)
    - itsr_ticket_number: varchar(100) (UNIQUE)
    - requestor: varchar(100)
    - handler: varchar(100)
    - ticket_status: varchar(100)  -- 工单状态 (complete/incomplete)
    - itsr_status: varchar(100)    -- ITSR状态 (open/close)
    - create_datetime: datetime(6)
    """
    __tablename__ = 'auto_tickets_itsr_network'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    itsr_ticket_number = Column(String(100), unique=True, nullable=False, comment='ITSR编号')
    requestor = Column(String(100), nullable=False, comment='请求人')
    handler = Column(String(100), nullable=False, comment='处理人')
    ticket_status = Column(String(100), nullable=False, comment='工单状态: complete/incomplete')
    itsr_status = Column(String(100), nullable=False, comment='ITSR状态: open/close')
    create_datetime = Column(DateTime(6), nullable=False, comment='创建时间')
    
    def __repr__(self):
        return f"<ITSRNetworkTicket(itsr_ticket_number='{self.itsr_ticket_number}', ticket_status='{self.ticket_status}', itsr_status='{self.itsr_status}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'itsr_ticket_number': self.itsr_ticket_number,
            'requestor': self.requestor,
            'handler': self.handler,
            'ticket_status': self.ticket_status,
            'itsr_status': self.itsr_status,
            'create_datetime': self.create_datetime.isoformat() if self.create_datetime else None,
        }


# ============================================================================
# 数据库管理器
# ============================================================================
class DBManager:
    """数据库管理器"""
    
    def __init__(self, config: DBConfig = None):
        self.config = config or DBConfig.from_env()
        self.engine = None
        self.SessionLocal = None
        self._connect()
    
    def _connect(self):
        """建立数据库连接"""
        try:
            self.engine = create_engine(
                self.config.connection_url,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
                echo=False  # 设为 True 可以看到 SQL 语句
            )
            self.SessionLocal = sessionmaker(bind=self.engine)
            logger.info(f"数据库连接成功: {self.config.host}:{self.config.port}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False
    
    # ===== CRUD 操作 =====
    
    def get_ticket_by_number(self, itsr_ticket_number: str) -> Optional[ITSRNetworkTicket]:
        """根据 ITSR 编号获取工单"""
        session = self.get_session()
        try:
            ticket = session.query(ITSRNetworkTicket).filter_by(
                itsr_ticket_number=itsr_ticket_number
            ).first()
            return ticket
        finally:
            session.close()
    
    def get_all_tickets(self, limit: int = 100) -> List[ITSRNetworkTicket]:
        """获取所有工单"""
        session = self.get_session()
        try:
            tickets = session.query(ITSRNetworkTicket).order_by(
                ITSRNetworkTicket.id.desc()
            ).limit(limit).all()
            return tickets
        finally:
            session.close()
    
    def get_pending_close_tickets(self) -> List[ITSRNetworkTicket]:
        """
        获取待关闭的工单
        条件: ticket_status='complete' AND itsr_status='open'
        """
        session = self.get_session()
        try:
            tickets = session.query(ITSRNetworkTicket).filter_by(
                ticket_status='complete',
                itsr_status='open'
            ).order_by(ITSRNetworkTicket.id.desc()).all()
            return tickets
        finally:
            session.close()
    
    def get_pending_close_ticket_numbers(self) -> List[str]:
        """
        获取待关闭的工单编号列表
        条件: ticket_status='complete' AND itsr_status='open'
        """
        tickets = self.get_pending_close_tickets()
        return [t.itsr_ticket_number for t in tickets]
    
    def update_itsr_status(self, itsr_ticket_number: str, new_status: str) -> bool:
        """
        更新工单的 itsr_status
        
        Args:
            itsr_ticket_number: ITSR编号
            new_status: 新状态 (open/close)
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("UPDATE auto_tickets_itsr_network SET itsr_status = :status WHERE itsr_ticket_number = :number"),
                    {"status": new_status, "number": itsr_ticket_number}
                )
                conn.commit()
                if result.rowcount > 0:
                    logger.info(f"更新工单状态: {itsr_ticket_number} -> itsr_status={new_status}")
                    return True
                else:
                    logger.warning(f"工单不存在: {itsr_ticket_number}")
                    return False
        except SQLAlchemyError as e:
            logger.error(f"更新工单状态失败: {e}")
            return False
    
    def mark_itsr_closed(self, itsr_ticket_number: str) -> bool:
        """标记工单为已关闭 (itsr_status='closed')"""
        return self.update_itsr_status(itsr_ticket_number, 'closed')
    
    # ===== 统计查询 =====
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        session = self.get_session()
        try:
            total = session.query(ITSRNetworkTicket).count()
            itsr_open = session.query(ITSRNetworkTicket).filter_by(itsr_status='open').count()
            itsr_closed = session.query(ITSRNetworkTicket).filter_by(itsr_status='closed').count()
            ticket_complete = session.query(ITSRNetworkTicket).filter_by(ticket_status='complete').count()
            ticket_incomplete = session.query(ITSRNetworkTicket).filter_by(ticket_status='incomplete').count()
            pending_close = session.query(ITSRNetworkTicket).filter_by(
                ticket_status='complete', itsr_status='open'
            ).count()
            
            return {
                "total": total,
                "itsr_open": itsr_open,
                "itsr_closed": itsr_closed,
                "ticket_complete": ticket_complete,
                "ticket_incomplete": ticket_incomplete,
                "pending_close": pending_close
            }
        finally:
            session.close()
    
    def execute_raw_sql(self, sql: str) -> List[Dict]:
        """执行原生 SQL 查询"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = result.keys()
                rows = [dict(zip(columns, row)) for row in result.fetchall()]
                return rows
        except SQLAlchemyError as e:
            logger.error(f"执行 SQL 失败: {e}")
            return []


# ============================================================================
# 便捷函数
# ============================================================================
_db_manager: Optional[DBManager] = None


def get_db_manager(config: DBConfig = None) -> DBManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DBManager(config)
    return _db_manager


# ============================================================================
# 命令行测试
# ============================================================================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ITSR 数据库管理工具")
    parser.add_argument("--test", action="store_true", help="测试数据库连接")
    parser.add_argument("--list", action="store_true", help="列出所有工单记录")
    parser.add_argument("--pending", action="store_true", help="列出待关闭的工单")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--query", metavar="ITSR", help="查询工单记录")
    parser.add_argument("--sql", metavar="SQL", help="执行原生 SQL")
    
    args = parser.parse_args()
    
    try:
        db = get_db_manager()
        
        if args.test:
            if db.test_connection():
                print("✅ 数据库连接成功")
            else:
                print("❌ 数据库连接失败")
        
        elif args.list:
            tickets = db.get_all_tickets()
            print(f"\n共 {len(tickets)} 条记录:\n")
            print(f"{'ID':<6} {'ITSR编号':<20} {'处理人':<15} {'工单状态':<12} {'ITSR状态':<10}")
            print("-" * 70)
            for t in tickets:
                print(f"{t.id:<6} {t.itsr_ticket_number:<20} {t.handler:<15} {t.ticket_status:<12} {t.itsr_status:<10}")
        
        elif args.pending:
            tickets = db.get_pending_close_tickets()
            print(f"\n待关闭工单（共 {len(tickets)} 条）:\n")
            print(f"{'ID':<6} {'ITSR编号':<20} {'处理人':<15} {'工单状态':<12} {'ITSR状态':<10}")
            print("-" * 70)
            for t in tickets:
                print(f"{t.id:<6} {t.itsr_ticket_number:<20} {t.handler:<15} {t.ticket_status:<12} {t.itsr_status:<10}")
        
        elif args.stats:
            stats = db.get_statistics()
            print("\n📊 统计信息:")
            print(f"   总数: {stats['total']}")
            print(f"   ITSR Open: {stats['itsr_open']}")
            print(f"   ITSR Closed: {stats['itsr_closed']}")
            print(f"   工单 Complete: {stats['ticket_complete']}")
            print(f"   工单 Incomplete: {stats['ticket_incomplete']}")
            print(f"   🔴 待关闭: {stats['pending_close']}")
        
        elif args.query:
            ticket = db.get_ticket_by_number(args.query)
            if ticket:
                import json
                print(json.dumps(ticket.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(f"未找到: {args.query}")
        
        elif args.sql:
            results = db.execute_raw_sql(args.sql)
            import json
            print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

