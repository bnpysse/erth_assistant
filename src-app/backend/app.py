# [ANCHOR: CH-04]
# Description: Robyn 后端边车服务入口，引入基于 Opaque Token 的鉴权拦截中间件与 CORS 许可白名单，锁死物理通信权限。
# Status: Verified

import os
from robyn import Robyn, Request, Response, ALLOW_CORS
from robyn.types import PathParams
from db import init_db, engine, Todo, get_active_todos, add_todo, toggle_todo_status, soft_delete_todo
from sqlmodel import Session, select
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
        with Session(engine) as session:
            statement = select(Todo).where(Todo.is_deleted == 0).limit(1)
            result = session.exec(statement).first()
            if result:
                status = "success"
                db_msg = f"Connected. Active sentinel title: {result.title}"
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
                        "database": "sqlmodel",
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

@app.get("/api/v1/todos")
async def get_todos(request: Request):
    try:
        todos = await get_active_todos()
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps(todos)
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"error": str(e)})
        )

@app.post("/api/v1/todos")
async def create_todo(request: Request):
    try:
        try:
            body = request.json()
        except Exception:
            body = json.loads(request.body) if request.body else {}
            
        title = body.get("title")
        if not title:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Missing field: title"})
            )
            
        todo = await add_todo(title)
        return Response(
            status_code=201,
            headers={"Content-Type": "application/json"},
            description=json.dumps(todo)
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"error": str(e)})
        )

@app.put("/api/v1/todos/:id/toggle")
async def toggle_todo(request: Request, id: str):
    try:
        todo_id = id
        if not todo_id:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Missing parameter: id"})
            )
            
        todo = await toggle_todo_status(todo_id)
        if todo is None:
            return Response(
                status_code=404,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Todo not found or already deleted"})
            )
            
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps(todo)
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"error": str(e)})
        )

@app.delete("/api/v1/todos/:id")
async def delete_todo(request: Request, id: str):
    try:
        todo_id = id
        if not todo_id:
            return Response(
                status_code=400,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Missing parameter: id"})
            )
            
        success = await soft_delete_todo(todo_id)
        if not success:
            return Response(
                status_code=404,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Todo not found or already deleted"})
            )
            
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"status": "success", "message": f"Todo {todo_id} soft deleted"})
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"error": str(e)})
        )


if __name__ == "__main__":
    # 使用 Port 0 启动，操作系统分配空闲随机端口，杜绝冲突硬编码
    # 真实运行端口会打印到 stdout 供前端捕获
    app.start(host="127.0.0.1", port=0)
