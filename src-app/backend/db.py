import os
import time
import uuid
from sqlmodel import Field, SQLModel, create_engine, Session, select
import sqlalchemy_libsql  # 注册 sqlite+libsql 方言以支持 Turso 远程连接

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local_edge.db")

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
