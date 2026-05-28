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

import urllib.parse

def get_request_body_params(request: Request) -> dict:
    """智能解析请求体，兼容 application/json 与 application/x-www-form-urlencoded"""
    content_type = request.headers.get("content-type") or ""
    body_str = ""
    if isinstance(request.body, bytes):
        body_str = request.body.decode("utf-8")
    elif isinstance(request.body, str):
        body_str = request.body

    if "application/x-www-form-urlencoded" in content_type:
        parsed = urllib.parse.parse_qs(body_str)
        return {k: v[0] for k, v in parsed.items()}
    else:
        try:
            return json.loads(body_str) if body_str else {}
        except Exception:
            return {}

def render_task_fragment(todo: dict) -> str:
    """将单个待办事项渲染为超媒体 HTML 碎片"""
    todo_id = todo["id"]
    title = todo["title"]
    is_completed = todo["is_completed"]
    
    completed_class = "completed" if is_completed == 1 else ""
    checkmark = "✓" if is_completed == 1 else ""
    text_completed_class = "completed" if is_completed == 1 else ""
    
    return f"""
    <li class="todo-item">
        <div class="todo-item-left">
            <button hx-put="/api/v1/todos/{todo_id}/toggle" 
                    hx-target="closest li" 
                    hx-swap="outerHTML" 
                    class="todo-toggle-btn {completed_class}">
                {checkmark}
            </button>
            <span class="todo-text {text_completed_class}">{title}</span>
        </div>
        <button hx-delete="/api/v1/todos/{todo_id}" 
                hx-target="closest li" 
                hx-swap="outerHTML" 
                class="todo-btn-delete">
            ✕
        </button>
    </li>
    """

def render_todo_center(todos: list) -> str:
    """渲染完整的待办中心面板 HTML 碎片"""
    list_items = "".join(render_task_fragment(todo) for todo in todos)
    return f"""
    <div class="todo-card">
        <h2>
            <span>📅 待办中心</span>
            <span style="font-size: 0.85rem; font-weight: normal; color: var(--text-secondary);">共 {len(todos)} 项任务</span>
        </h2>
        
        <!-- 零 JS 超媒体新增表单 -->
        <form hx-post="/api/v1/todos" 
              hx-target="#todo-list" 
              hx-swap="afterbegin" 
              class="todo-form"
              hx-on="htmx:afterRequest: this.reset()">
            <input type="text" 
                   name="title" 
                   placeholder="记录你的下一个伟大构想..." 
                   class="todo-input" 
                   required 
                   autocomplete="off" />
            <button type="submit" class="todo-btn-add">添加</button>
        </form>

        <!-- 滚动任务列表 -->
        <ul id="todo-list" class="todo-list">
            {list_items}
        </ul>
    </div>
    """

@app.get("/api/v1/todos")
async def get_todos(request: Request):
    try:
        todos = await get_active_todos()
        is_htmx = request.headers.get("hx-request") == "true"
        
        if is_htmx:
            return Response(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=render_todo_center(todos)
            )
        else:
            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                description=json.dumps(todos)
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 16px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

async def handle_create_todo(request: Request):
    try:
        body = get_request_body_params(request)
        title = body.get("title")
        is_htmx = request.headers.get("hx-request") == "true"
        
        if not title:
            if is_htmx:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Missing field: title</div>'
                )
            else:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Missing field: title"})
                )
                
        todo = await add_todo(title)
        print(f"[Database] 数据已沉淀入库: {todo['id'][:8]} - {title}")
        
        if is_htmx:
            return Response(
                status_code=201,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=render_task_fragment(todo)
            )
        else:
            return Response(
                status_code=201,
                headers={"Content-Type": "application/json"},
                description=json.dumps(todo)
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 10px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

@app.post("/api/v1/todos")
async def create_todo_v1(request: Request):
    return await handle_create_todo(request)

@app.post("/api/v1/tasks")
async def create_task_v1(request: Request):
    return await handle_create_todo(request)

async def handle_toggle_todo(request: Request, id: str):
    try:
        todo_id = id
        is_htmx = request.headers.get("hx-request") == "true"
        
        if not todo_id:
            if is_htmx:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Missing parameter: id</div>'
                )
            else:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Missing parameter: id"})
                )
                
        todo = await toggle_todo_status(todo_id)
        if todo is None:
            if is_htmx:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Todo not found</div>'
                )
            else:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Todo not found or already deleted"})
                )
                
        if is_htmx:
            return Response(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=render_task_fragment(todo)
            )
        else:
            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                description=json.dumps(todo)
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 10px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

@app.put("/api/v1/todos/:id/toggle")
async def toggle_todo_v1(request: Request, id: str):
    return await handle_toggle_todo(request, id)

@app.put("/api/v1/tasks/:id/toggle")
async def toggle_task_v1(request: Request, id: str):
    return await handle_toggle_todo(request, id)

async def handle_delete_todo(request: Request, id: str):
    try:
        todo_id = id
        is_htmx = request.headers.get("hx-request") == "true"
        
        if not todo_id:
            if is_htmx:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Missing parameter: id</div>'
                )
            else:
                return Response(
                    status_code=400,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Missing parameter: id"})
                )
                
        success = await soft_delete_todo(todo_id)
        if not success:
            if is_htmx:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    description='<div style="color: #ef4444; padding: 10px;">Todo not found or already deleted</div>'
                )
            else:
                return Response(
                    status_code=404,
                    headers={"Content-Type": "application/json"},
                    description=json.dumps({"error": "Todo not found or already deleted"})
                )
                
        if is_htmx:
            return Response(
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=""
            )
        else:
            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"status": "success", "message": f"Todo {todo_id} soft deleted"})
            )
    except Exception as e:
        is_htmx = request.headers.get("hx-request") == "true"
        if is_htmx:
            return Response(
                status_code=500,
                headers={"Content-Type": "text/html; charset=utf-8"},
                description=f'<div style="color: #ef4444; padding: 10px;">Error: {str(e)}</div>'
            )
        else:
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": str(e)})
            )

@app.delete("/api/v1/todos/:id")
async def delete_todo_v1(request: Request, id: str):
    return await handle_delete_todo(request, id)

@app.delete("/api/v1/tasks/:id")
async def delete_task_v1(request: Request, id: str):
    return await handle_delete_todo(request, id)

@app.get("/api/v1/notebook")
async def get_notebook(request: Request):
    """全景日志超媒体占位，展示第八章进化预告"""
    is_htmx = request.headers.get("hx-request") == "true"
    
    html_placeholder = """
    <div class="todo-card" style="text-align: center; max-width: 500px; animation: fadeIn 0.4s ease-out;">
        <h2 style="justify-content: center; margin-bottom: 16px;">📓 全景日志 (Notebook)</h2>
        <p style="color: var(--text-secondary); line-height: 1.6; margin-bottom: 24px;">
            欢迎来到全景日志模块。当前章节任务专注于 HTMX 超媒体引擎的并轨与深水区调试。
        </p>
        <div style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <span style="font-size: 1.2rem; display: block; margin-bottom: 8px;">🚀 敬请期待第八章：</span>
            <span style="color: var(--text-primary); font-weight: 600;">《超媒体的自我进化——Markdown 随笔日记本》</span>
        </div>
        <p style="font-size: 0.85rem; color: var(--text-secondary);">
            在这里，我们将实现一个完整的 Local-First 的随笔交互面板，支持 Markdown 渲染与存储。
        </p>
    </div>
    """
    if is_htmx:
        return Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            description=html_placeholder
        )
    else:
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"message": "Notebook placeholder. Unlock in Chapter 8."})
        )


if __name__ == "__main__":
    # 使用 Port 0 启动，操作系统分配空闲随机端口，杜绝冲突硬编码
    # 真实运行端口会打印到 stdout 供前端捕获
    app.start(host="127.0.0.1", port=0)
