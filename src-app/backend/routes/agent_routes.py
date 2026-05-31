from robyn import SubRouter, Request, Response, router
from robyn.responses import StreamingResponse as PyStreamingResponse
from robyn.robyn import StreamingResponse as RustStreamingResponse
import json

# ==========================================
# Monkeypatch Robyn 0.84.0 StreamingResponse Bug
# Robyn's _format_response returns the Py wrapper instead of the Rust object
original_format_response = router.Router._format_response

def patched_format_response(self, res):
    if isinstance(res, PyStreamingResponse):
        return RustStreamingResponse(
            status_code=res.status_code,
            headers=res.headers,
            media_type=res.media_type,
            content=res.content
        )
    if isinstance(res, RustStreamingResponse):
        return res
    return original_format_response(self, res)

router.Router._format_response = patched_format_response
# ==========================================

from services.action_registry import ActionRegistry

agent_router = SubRouter(__name__)

@agent_router.get("/api/v1/agent/schemas")
async def get_action_schemas(request: Request):
    """
    语义意图捕获管线：
    向大模型暴露当前已挂载的所有原子化 Action Schemas
    """
    schemas = ActionRegistry.get_all_schemas()
    return Response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        description=json.dumps({"schemas": schemas})
    )

@agent_router.post("/api/v1/agent/execute")
async def execute_action(request: Request):
    """
    语义意图到物理执行的转换：
    接收大模型 Function Calling 回传的 JSON，执行物理方法并返回结果。
    """
    try:
        body_str = request.body.decode("utf-8") if isinstance(request.body, (bytes, bytearray)) else request.body
        payload = json.loads(body_str) if body_str else {}
        
        action_name = payload.get("action")
        arguments = payload.get("arguments", {})
        
        if not action_name:
            return Response(status_code=400, headers={"Content-Type": "application/json"}, description='{"error": "Missing action name"}')
            
        print(f"[Agent Runtime] ⚡ 意图触发: {action_name} | Params: {arguments}")
        
        # 物理执行
        result = await ActionRegistry.execute(action_name, arguments)
        
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"action": action_name, "result": result})
        )
    except Exception as e:
        return Response(
            status_code=500,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"error": str(e)})
        )

# [ANCHOR: CH-13] 手写 AI 工具闭环循环与 HTMX SSE 流式打字机落地
import asyncio
from services.llm_client import async_llm_chat_stream
import uuid
import urllib.parse
import html

# 本地轻量化会话轮询队列（FIFO）
_chat_sessions = {}

def render_chat_message(role, content):
    if role == "user":
        return f"<div class='chat-msg user' style='text-align: right; margin: 10px 0;'><span style='background: var(--bg-card); padding: 8px 12px; border-radius: 12px; display: inline-block; border: 1px solid var(--border-color);'>{html.escape(content)}</span></div>"
    return ""

def render_chat_ui():
    """AI 控制台的基础框架"""
    # 不再使用 hx-post/sse 等 HTMX 扩展，我们只留下基本的 HTML 骨架，并赋予其纯净的 ID 供原生物理 fetch 劫持。
    return """
    <div style="display: flex; flex-direction: column; height: calc(100vh - 80px); width: 100%; max-width: 900px; background: rgba(27, 33, 47, 0.7); border: 1px solid var(--border-color); border-radius: 16px; padding: 24px; box-sizing: border-box; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); backdrop-filter: blur(12px);">
        <h2 style="margin-top: 0; color: var(--accent-color); border-bottom: 1px solid var(--border-color); padding-bottom: 12px; display: flex; justify-content: space-between;">
            <span>🤖 AI 控制台</span>
            <span style="font-size: 0.8rem; color: var(--text-secondary); font-weight: normal; margin-top: 8px;">(Local OLLAMA ReAct / Pure Fetch Stream)</span>
        </h2>
        
        <div id="chat-history" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding: 12px 0;">
            <div style="text-align: center; color: var(--text-secondary); margin-bottom: 20px; font-size: 0.9rem;">会话初始化完成。等待物理指令...</div>
        </div>

        <form id="chat-form" style="display: flex; gap: 12px; margin-top: 16px;">
            <input type="text" name="msg" placeholder="输入指令，例如：当前的绝对物理时间是多少？" required 
                   style="flex: 1; background: #0b0e14; border: 1px solid var(--border-color); border-radius: 8px; padding: 12px 16px; color: var(--text-primary); outline: none; transition: border-color 0.3s;" onfocus="this.style.borderColor='var(--accent-color)'" onblur="this.style.borderColor='var(--border-color)'">
            <button type="submit" style="background: var(--accent-color); color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='var(--accent-hover)'" onmouseout="this.style.background='var(--accent-color)'">发送指令</button>
        </form>
    </div>
    """

@agent_router.get("/api/v1/agent/chat_ui")
def get_chat_ui(request: Request):
    return Response(status_code=200, headers={"Content-Type": "text/html; charset=utf-8"}, description=render_chat_ui())

@agent_router.post("/api/v1/agent/chat_stream")
async def chat_stream_endpoint(request: Request):
    """
    [锚点：CH-13 原生 Fetch 流式投递]
    完全废弃 SSE (Server-Sent Events) 的 data: 前缀包装。
    因为原生 macOS WebKit 在沙盒的 views:// 协议下发起跨域 EventSource 极易触发 0xBAD4007 内核崩溃。
    此处改为纯粹的 Chunked HTML 碎片直出，由前端 fetch API 解析拼装。
    """
    try:
        body_str = request.body.decode("utf-8") if isinstance(request.body, (bytes, bytearray)) else request.body
        payload = json.loads(body_str) if body_str else {}
        user_msg = payload.get("msg", "")
    except:
        user_msg = ""

    session_id = "default"
    
    if session_id not in _chat_sessions:
        _chat_sessions[session_id] = [
            {"role": "system", "content": "你是 ERTH Assistant，一个强大的本地 AI 智能体。你具备工具调用（Function Calling）能力。如果用户询问当前时间，你必须调用 `get_system_time` 工具来获取准确时间，然后回答用户。你的回答应该简明扼要。"}
        ]
        
    session_hist = _chat_sessions[session_id]
    session_hist.append({"role": "user", "content": user_msg})
    
    # 历史裁切：保留 System Prompt + 最近的 20 条上下文
    if len(session_hist) > 21:
        _chat_sessions[session_id] = [session_hist[0]] + session_hist[-20:]

    async def html_generator():
        # [Hack: Force Actix-web to flush TCP buffer]
        padding = "<!-- " + ("x" * 4096) + " -->"
        yield padding + "<div style='color: #10b981; font-family: monospace; font-size: 0.85rem; margin-bottom: 8px; opacity: 0.7;'>&gt; [System] 物理引擎连接中... (若冷启动模型，首次唤醒可能需要 1~2 分钟)</div>\n"
        while True:
            tools = ActionRegistry.get_all_schemas()
            
            try:
                response = await async_llm_chat_stream(
                    messages=session_hist,
                    tools=tools if tools else None
                )
            except Exception as e:
                yield padding + f"<div style='color: #ef4444; font-family: monospace; font-size: 0.85rem; margin-bottom: 12px;'>&gt; [System] 引擎连接失败 (超时或Ollama未启动): {html.escape(str(e))}</div>\n"
                break
            # 不再进行 pre_consume 阻塞判断，全量进入流式解析
            # 无论是纯文本、Preamble + Tool Call 还是纯 Tool Call，都先完整过一遍流
            yield "<!--MKD_START-->\n"
            
            async for chunk in response.text_stream():
                yield chunk + padding
            
            # 流结束后，如果有 preamble 纯文本，大模型本身就会在 final_text 留下痕迹
            assistant_msg = {"role": "assistant", "content": response.final_text if response.final_text else None}
            
            # 流式处理完毕，如果有截获的 tool_call，开始处理物理逻辑
            if response.is_tool_call:
                tool_name = response.tool_name
                tool_args = response.tool_args
                
                log_msg = f"&gt; [System] 物理动作调用截获: {tool_name}"
                if tool_args:
                    log_msg += f" | Payload: {html.escape(str(tool_args))}"
                    
                yield f"<div style='color: var(--accent-color); font-family: monospace; font-size: 0.85rem; margin-bottom: 8px; border-bottom: 1px dashed var(--accent-color); padding-bottom: 4px;'>{log_msg}</div>\n"
                
                try:
                    result = await ActionRegistry.execute(tool_name, tool_args)
                    result_str = str(result)
                    yield f"<div style='color: #10b981; font-family: monospace; font-size: 0.85rem; margin-bottom: 12px; opacity: 0.8;'>&gt; [System] 动作返回: {html.escape(result_str)[:200]}...</div>\n"
                except Exception as e:
                    result_str = f"Error: {str(e)}"
                    yield f"<div style='color: #ef4444; font-family: monospace; font-size: 0.85rem; margin-bottom: 12px;'>&gt; [System] 执行崩溃: {html.escape(result_str)}</div>\n"
                
                # 为 assistant_msg 附加上 tool_calls 信息
                assistant_msg["tool_calls"] = [{"id": response.tool_id, "type": "function", "function": {"name": tool_name, "arguments": json.dumps(tool_args)}}]
                session_hist.append(assistant_msg)
                
                # 记录动作执行结果
                session_hist.append({
                    "role": "tool",
                    "tool_call_id": response.tool_id,
                    "name": tool_name,
                    "content": result_str
                })
                # 动作执行完毕，重新回旋让大模型继续思考或总结
                continue
            else:
                # 纯粹的聊天回复，没有 tool_call，则结束当前流
                session_hist.append(assistant_msg)
                break

    return PyStreamingResponse(
        content=html_generator(),
        status_code=200,
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        media_type="text/html"
    )
