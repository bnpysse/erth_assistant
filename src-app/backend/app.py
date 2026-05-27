# [ANCHOR: CH-02]
# Description: Robyn 后端边车服务入口，配置 Port 0 以供操作系统随机分配，注册本地数据库初始化与 health 心跳检测。
# Status: Verified

from robyn import Robyn, Request, Response
from db import init_db, get_db_client
import json

app = Robyn(__file__)

@app.startup_handler
async def startup():
    """后端点火时自动初始化本地 libSQL 数据基盘"""
    try:
        await init_db()
        print("[Robyn Backend] Local-First db基盘筑底成功！")
    except Exception as e:
        print(f"[ERROR] 数据库基盘初始化失败: {e}")

@app.get("/api/v1/health")
async def health_check(request: Request):
    """
    心跳健康检查
    -----------
    不仅返回服务状态，更深入数据层执行连通性测试，向主进程上报真实状态
    """
    try:
        client = get_db_client()
        # 测试读取哨兵数据
        result = await client.execute("SELECT id, title FROM todos WHERE is_deleted = 0 LIMIT 1")
        if len(result.rows) > 0:
            status = "success"
            db_msg = f"Connected. Active sentinel title: {result.rows[0]['title']}"
        else:
            status = "warning"
            db_msg = "Connected, but no active tasks found."
            
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps({
                "status": status,
                "data": {
                    "service": "robyn-sidecar",
                    "database": "libsql",
                    "message": db_msg
                }
            })
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({
                "status": "error",
                "message": f"Database unavailable: {str(e)}"
            })
        )

if __name__ == "__main__":
    # 使用 Port 0 启动，操作系统分配空闲随机端口，杜绝冲突硬编码
    # 真实运行端口会打印到 stdout 供前端捕获
    app.start(host="127.0.0.1", port=0)
