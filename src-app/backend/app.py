# [ANCHOR: CH-04]
# Description: Robyn 后端边车服务入口，引入基于 Opaque Token 的鉴权拦截中间件与 CORS 许可白名单，锁死物理通信权限。
# Status: Verified

import os
from robyn import Robyn, Request, Response, ALLOW_CORS
from db import init_db, get_db_client
import json

app = Robyn(__file__)

# 在系统启动的破晓时刻，读取前端主进程静默注入的密钥
AGENT_SECRET_TOKEN = os.environ.get("AGENT_SECRET_TOKEN")

@app.before_request()
def auth_middleware(request: Request):
    # 跨域预检放行：如果是 OPTIONS 请求，必须直接放行给底层的路由器，规避管线锁死
    if request.method == "OPTIONS":
        return request
        
    auth_header = request.headers.get("authorization")
    expected_token = f"Bearer {AGENT_SECRET_TOKEN}"
    
    # 强制比对身份令牌，拦截非法流量并响应 403
    if not auth_header or auth_header != expected_token:
        return Response(
            status_code=403,
            headers={"Content-Type": "application/json"},
            description='{"error": "Forbidden: Invalid or Missing Opaque Token"}'
        )
        
    return request

# 启用官方 CORS，并显式放行授权及 HTMX 的全套特征 Headers
ALLOW_CORS(app, origins=["*"], headers=[
    "Authorization", "Content-Type", 
    "hx-target", "hx-current-url", "hx-request", "hx-trigger"
])

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

@app.get("/ping")
def ping(request: Request):
    """Watchdog 看门狗专属心跳探测端点，极低开销"""
    return Response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        description=json.dumps({"status": "pong"})
    )


if __name__ == "__main__":
    # 使用 Port 0 启动，操作系统分配空闲随机端口，杜绝冲突硬编码
    # 真实运行端口会打印到 stdout 供前端捕获
    app.start(host="127.0.0.1", port=0)
