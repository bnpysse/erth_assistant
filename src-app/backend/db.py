import os
import time
import uuid
import libsql_client

DB_FILE = "local_edge.db"
_client = None

def get_db_client() -> libsql_client.LibsqlClient:
    """获取 libSQL 客户端单例"""
    global _client
    if _client is None:
        _client = libsql_client.create_client(f"file:{DB_FILE}")
    return _client

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
    client = get_db_client()
    
    # 建立具备 UUIDv7 主键与 Tombstone 机制的本地表
    await client.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            is_deleted INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    
    # 写入一条系统哨兵测试数据 (若表为空)
    result = await client.execute("SELECT COUNT(*) as count FROM todos")
    if result.rows[0]["count"] == 0:
        sentinel_id = str(generate_uuidv7())
        now = int(time.time() * 1000)
        await client.execute(
            "INSERT INTO todos (id, title, is_deleted, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
            [sentinel_id, "ERTH Engine Database Initialized Successfully", now, now]
        )
