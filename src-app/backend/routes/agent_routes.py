from robyn import Router, Request, Response
import json
from services.action_registry import ActionRegistry

agent_router = Router()

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
