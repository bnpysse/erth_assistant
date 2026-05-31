# [ANCHOR: CH-05: SQLMODEL_DATABASE]
import os
import sys
import time
import uuid
from sqlmodel import Field, SQLModel, create_engine, Session, select
import sqlalchemy_libsql  # 注册 sqlite+libsql 方言以支持 Turso 远程连接

# [ANCHOR: CH-16: 数据库封存态环境寻址与云边同步]
if getattr(sys, 'frozen', False):
    app_data_dir = os.path.expanduser("~/.erth_assistant")
    os.makedirs(app_data_dir, exist_ok=True)
    db_path = os.path.join(app_data_dir, "local_edge.db")
else:
    db_path = "local_edge.db"

# Turso 云边同步配置 (Embedded Replicas)
turso_sync_url = os.environ.get("TURSO_SYNC_URL")
turso_auth_token = os.environ.get("TURSO_AUTH_TOKEN")

if turso_sync_url and turso_auth_token:
    # 启用云边同步模式 (Local-First + 远程同步)
    DATABASE_URL = f"sqlite+libsql:///{db_path}?syncUrl={turso_sync_url}&authToken={turso_auth_token}"
else:
    # 默认回退到纯本地 SQLite 模式
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{db_path}")

# SQLite 特殊连接参数配置
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# 实例化 SQLModel 引擎
engine = create_engine(DATABASE_URL, connect_args=connect_args)

class Todo(SQLModel, table=True):
    """待办事项数据模型"""
    __tablename__ = "todos"
    
    id: str = Field(primary_key=True)
    title: str
    is_completed: int = Field(default=0)
    is_deleted: int = Field(default=0)
    created_at: int
    updated_at: int

class Journal(SQLModel, table=True):
    """全景日志数据模型"""
    __tablename__ = "journals"
    
    id: str = Field(primary_key=True)
    title: str
    content: str
    is_deleted: int = Field(default=0)
    created_at: int
    updated_at: int

def generate_uuidv7() -> uuid.UUID:
    """
    手动实现 RFC 9562 兼容的 UUIDv7 生成器
    --------------------------------------
    结构：
    - time_low + time_mid (48 bits): 当前毫秒时间戳
    - version (4 bits): 固定为 7 (0111)
    - rand_a (12 bits): 伪随机数
    - variant (2 bits): 固定为 2 (10xx)
    - rand_b (62 bits): 伪随机数
    """
    timestamp_ms = int(time.time() * 1000)
    timestamp_bytes = timestamp_ms.to_bytes(6, byteorder='big')
    
    rand_bytes = bytearray(os.urandom(10))
    
    # 填充 version 7 (0x7000)
    rand_a = int.from_bytes(rand_bytes[0:2], byteorder='big') & 0x0FFF
    time_hi_and_version = (7 << 12) | rand_a
    
    # 填充 variant 2 (0x8000)
    rand_b = int.from_bytes(rand_bytes[2:4], byteorder='big') & 0x3FFF
    clk_seq_and_variant = 0x8000 | rand_b
    
    node = rand_bytes[4:10]
    
    return uuid.UUID(fields=(
        int.from_bytes(timestamp_bytes[0:4], byteorder='big'),
        int.from_bytes(timestamp_bytes[4:6], byteorder='big'),
        time_hi_and_version,
        clk_seq_and_variant >> 8,
        clk_seq_and_variant & 0xFF,
        int.from_bytes(node, byteorder='big')
    ))

async def init_db():
    """初始化本地数据库，建立 todos 表结构"""
    SQLModel.metadata.create_all(engine)
    
    # 写入一条系统哨兵测试数据 (若表为空)
    with Session(engine) as session:
        statement = select(Todo)
        results = session.exec(statement).all()
        if not results:
            sentinel_id = str(generate_uuidv7())
            now = int(time.time() * 1000)
            sentinel = Todo(
                id=sentinel_id,
                title="ERTH Engine Database Initialized Successfully",
                is_completed=0,
                is_deleted=0,
                created_at=now,
                updated_at=now
            )
            session.add(sentinel)
            session.commit()
            
    # 写入 Journal 种子数据 (若表为空)
    with Session(engine) as session:
        statement = select(Journal)
        if not session.exec(statement).all():
            now = int(time.time() * 1000)
            j1 = Journal(
                id=str(generate_uuidv7()), 
                title="晨间站会", 
                content="# 晨间站会\n\n- 昨日进展：\n- 今日计划：\n- 风险与阻碍：\n", 
                is_deleted=0, 
                created_at=now, 
                updated_at=now
            )
            j2 = Journal(
                id=str(generate_uuidv7()), 
                title="Bug 报告", 
                content="# Bug 报告\n\n- 现象描述：\n- 根因分析：\n- 修复方案：\n", 
                is_deleted=0, 
                created_at=now+1, 
                updated_at=now+1
            )
            session.add(j1)
            session.add(j2)
            session.commit()

async def get_active_todos() -> list:
    """获取所有未被逻辑删除的待办事项，按创建时间倒序排列"""
    with Session(engine) as session:
        statement = select(Todo).where(Todo.is_deleted == 0).order_by(Todo.created_at.desc())
        results = session.exec(statement).all()
        return [todo.model_dump() for todo in results]

async def add_todo(title: str) -> dict:
    """添加新的待办事项，生成 UUIDv7 并返回事项字典"""
    todo_id = str(generate_uuidv7())
    now = int(time.time() * 1000)
    todo = Todo(
        id=todo_id,
        title=title,
        is_completed=0,
        is_deleted=0,
        created_at=now,
        updated_at=now
    )
    with Session(engine) as session:
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo.model_dump()

async def toggle_todo_status(todo_id: str) -> dict | None:
    """翻转指定 ID 待办事项的完成状态，并更新时间戳"""
    with Session(engine) as session:
        todo = session.get(Todo, todo_id)
        if not todo or todo.is_deleted == 1:
            return None
        todo.is_completed = 1 if todo.is_completed == 0 else 0
        todo.updated_at = int(time.time() * 1000)
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo.model_dump()

async def soft_delete_todo(todo_id: str) -> bool:
    """标记待办事项为逻辑删除 (Tombstone)"""
    with Session(engine) as session:
        todo = session.get(Todo, todo_id)
        if not todo or todo.is_deleted == 1:
            return False
        todo.is_deleted = 1
        todo.updated_at = int(time.time() * 1000)
        session.add(todo)
        session.commit()
        return True

async def get_latest_journal() -> dict | None:
    """获取最新的一条未删除日志"""
    with Session(engine) as session:
        statement = select(Journal).where(Journal.is_deleted == 0).order_by(Journal.created_at.desc()).limit(1)
        result = session.exec(statement).first()
        return result.model_dump() if result else None

async def get_journal_history() -> list:
    """获取所有未删除日志的摘要"""
    with Session(engine) as session:
        statement = select(Journal).where(Journal.is_deleted == 0).order_by(Journal.created_at.desc())
        results = session.exec(statement).all()
        return [j.model_dump() for j in results]

async def get_specific_journal(journal_id: str) -> dict | None:
    """获取指定的日志"""
    with Session(engine) as session:
        journal = session.get(Journal, journal_id)
        if not journal or journal.is_deleted == 1:
            return None
        return journal.model_dump()

async def create_journal(title: str, content: str) -> dict:
    """创建并保存新日志"""
    journal_id = str(generate_uuidv7())
    now = int(time.time() * 1000)
    journal = Journal(
        id=journal_id,
        title=title,
        content=content,
        is_deleted=0,
        created_at=now,
        updated_at=now
    )
    with Session(engine) as session:
        session.add(journal)
        session.commit()
        session.refresh(journal)
        return journal.model_dump()

async def soft_delete_journal(journal_id: str) -> bool:
    """逻辑删除指定的日志"""
    with Session(engine) as session:
        journal = session.get(Journal, journal_id)
        if not journal or journal.is_deleted == 1:
            return False
        journal.is_deleted = 1
        journal.updated_at = int(time.time() * 1000)
        session.add(journal)
        session.commit()
        return True
