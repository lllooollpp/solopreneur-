"""
WebSocket 服务
实时推送 Agent 事件、聊天流式输出、工作流状态到前端
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from loguru import logger
import json
import asyncio
from typing import List
from datetime import datetime

router = APIRouter()


# ==================== 连接管理器 ====================

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 事件广播连接
        self.event_connections: List[WebSocket] = []
        # 聊天连接
        self.chat_connections: List[WebSocket] = []
        # 工作流连接
        self.flow_connections: List[WebSocket] = []
    
    async def connect_event(self, websocket: WebSocket):
        await websocket.accept()
        self.event_connections.append(websocket)
        logger.info(f"Event WebSocket connected, total: {len(self.event_connections)}")
    
    async def connect_chat(self, websocket: WebSocket):
        await websocket.accept()
        self.chat_connections.append(websocket)
        logger.info(f"Chat WebSocket connected, total: {len(self.chat_connections)}")
    
    async def connect_flow(self, websocket: WebSocket):
        await websocket.accept()
        self.flow_connections.append(websocket)
        logger.info(f"Flow WebSocket connected, total: {len(self.flow_connections)}")
    
    def disconnect_event(self, websocket: WebSocket):
        if websocket in self.event_connections:
            self.event_connections.remove(websocket)
        logger.info(f"Event WebSocket disconnected, remaining: {len(self.event_connections)}")
    
    def disconnect_chat(self, websocket: WebSocket):
        if websocket in self.chat_connections:
            self.chat_connections.remove(websocket)
        logger.info(f"Chat WebSocket disconnected, remaining: {len(self.chat_connections)}")
    
    def disconnect_flow(self, websocket: WebSocket):
        if websocket in self.flow_connections:
            self.flow_connections.remove(websocket)
        logger.info(f"Flow WebSocket disconnected, remaining: {len(self.flow_connections)}")
    
    async def broadcast_event(self, message: dict):
        """向所有事件连接广播消息"""
        disconnected = []
        for connection in self.event_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast event: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.event_connections.remove(conn)
    
    async def broadcast_flow(self, message: dict):
        """向所有工作流连接广播消息"""
        disconnected = []
        for connection in self.flow_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to flow connection: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.flow_connections.remove(conn)


manager = ConnectionManager()


# ==================== Agent 实例（保持原有 agent 调用）====================

_agent_loop = None
_agent_loop_lock = asyncio.Lock()


async def get_agent_loop():
    """
    获取或创建 AgentLoop 实例（支持工具调用），线程安全。

    使用组件管理器统一管理
    """
    from nanobot.core.dependencies import get_component_manager
    manager = get_component_manager()
    return await manager.get_agent_loop()


# ==================== 工作流状态管理 ====================

class WorkflowState:
    """工作流状态"""
    
    def __init__(self):
        self.task_stack: list[dict] = []
        self.snapshots: list[dict] = []
        self._snapshot_id = 0
    
    def add_task(self, name: str, description: str = ""):
        """添加任务到栈"""
        task = {
            "name": name,
            "description": description,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        self.task_stack.append(task)
        return task
    
    def update_task_status(self, index: int, status: str):
        """更新任务状态"""
        if 0 <= index < len(self.task_stack):
            self.task_stack[index]["status"] = status
            return self.task_stack[index]
        return None
    
    def pop_task(self):
        """完成并移除栈顶任务"""
        if self.task_stack:
            task = self.task_stack.pop()
            task["status"] = "completed"
            self._add_snapshot(f"完成任务: {task['name']}")
            return task
        return None
    
    def _add_snapshot(self, summary: str):
        """添加快照"""
        self._snapshot_id += 1
        snapshot = {
            "id": str(self._snapshot_id),
            "timestamp": datetime.now().isoformat(),
            "summary": summary
        }
        self.snapshots.insert(0, snapshot)
        if len(self.snapshots) > 50:
            self.snapshots = self.snapshots[:50]
    
    def get_state(self) -> dict:
        """获取当前状态"""
        return {
            "taskStack": self.task_stack,
            "snapshots": self.snapshots
        }
    
    def clear(self):
        """清空状态"""
        self.task_stack = []
        self.snapshots = []


# 全局工作流状态
workflow_state = WorkflowState()


# ==================== WebSocket 认证 ====================

def _get_ws_token_from_env() -> str | None:
    """从环境变量获取WebSocket token。"""
    import os
    return os.getenv("NANOBOT_WS_TOKEN")


async def _verify_websocket_token(websocket: WebSocket, token: str | None = None) -> bool:
    """验证WebSocket token。如果未设置环境变量则跳过验证。"""
    env_token = _get_ws_token_from_env()
    
    # 如果没有设置环境变量，则不需要验证（开发模式）
    if env_token is None:
        logger.debug("WebSocket token not configured, allowing connection")
        return True
    
    # 如果设置了环境变量，必须提供正确的token
    if token is None or token != env_token:
        logger.warning(f"WebSocket authentication failed for {websocket.client}")
        await websocket.close(code=1008, reason="Authentication failed")
        return False
    
    return True


# ==================== WebSocket 端点 ====================

@router.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(None)):
    """
    事件 WebSocket 端点，用于实时推送 Agent 事件
    需要提供 token 参数（如果设置了 NANOBOT_WS_TOKEN 环境变量）
    """
    # 先接受连接，然后验证
    await websocket.accept()
    
    # 验证token
    if not await _verify_websocket_token(websocket, token):
        return
    
    manager.event_connections.append(websocket)
    logger.info(f"Event WebSocket connected, total: {len(manager.event_connections)}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        manager.disconnect_event(websocket)
    except Exception as e:
        logger.error(f"Event WebSocket error: {e}")
        manager.disconnect_event(websocket)


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket, token: str | None = Query(None)):
    """
    聊天 WebSocket 端点 - 流式输出
    需要提供 token 参数（如果设置了 NANOBOT_WS_TOKEN 环境变量）
    
    消息格式:
    - 客户端: {"type": "message", "content": "消息", "model": "gpt-4o"}
    - 客户端: {"type": "clear"} - 清空历史
    - 服务端: {"type": "chunk", "content": "片段"}
    - 服务端: {"type": "done", "content": "完整回复"}
    - 服务端: {"type": "error", "content": "错误"}
    """
    # 先接受连接，然后验证
    await websocket.accept()
    
    # 验证token
    if not await _verify_websocket_token(websocket, token):
        return
    
    manager.chat_connections.append(websocket)
    logger.info(f"Chat WebSocket connected, total: {len(manager.chat_connections)}")
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")
            session_id = data.get("session_id", "default")
            session_key = f"web:{session_id}"
            
            if msg_type == "clear":
                try:
                    agent_loop = await get_agent_loop()
                    agent_loop.sessions.delete(session_key)
                except Exception as e:
                    logger.warning(f"Failed to clear session {session_key}: {e}")
                await websocket.send_json({
                    "type": "system",
                    "content": "对话历史已清空"
                })
                continue
            
            if msg_type != "message":
                continue
            
            content = data.get("content", "").strip()
            if not content:
                continue
            
            model = data.get("model")
            
            logger.info(f"WebSocket chat: {content[:50]}... (session: {session_key})")
            
            try:
                agent_loop = await get_agent_loop()

                # 临时覆盖模型（可选）
                original_model = agent_loop.model
                try:
                    if model:
                        agent_loop.model = model

                    async def send_chunk(text: str):
                        await websocket.send_json({
                            "type": "chunk",
                            "content": text
                        })

                    async def send_trace(event: dict):
                        # 将 trace 事件转发到前端
                        await websocket.send_json({
                            "type": "trace",
                            **event
                        })
                        # 工具调用和角色委派事件同时作为 activity 发送到聊天流
                        evt = event.get("event", "")
                        if evt in ("tool_start", "tool_end"):
                            await websocket.send_json({
                                "type": "activity",
                                "activity_type": evt,
                                "tool_name": event.get("tool_name", ""),
                                "tool_args": event.get("tool_args", {}),
                                "duration_ms": event.get("duration_ms"),
                                "result_length": event.get("result_length"),
                                "iteration": event.get("iteration"),
                                "timestamp": event.get("timestamp"),
                            })
                        elif evt in ("llm_start", "llm_end"):
                            await websocket.send_json({
                                "type": "activity",
                                "activity_type": evt,
                                "iteration": event.get("iteration"),
                                "model": event.get("model", ""),
                                "duration_ms": event.get("duration_ms"),
                                "total_tokens": event.get("total_tokens"),
                                "timestamp": event.get("timestamp"),
                            })

                    response_text = await agent_loop.process_direct_stream(
                        content=content,
                        session_key=session_key,
                        on_chunk=send_chunk,
                        on_trace=send_trace,
                    )
                finally:
                    agent_loop.model = original_model

                await websocket.send_json({
                    "type": "done",
                    "content": response_text
                })
            except Exception as e:
                logger.error(f"Chat API error: {e!r}")
                error_text = str(e) or repr(e)
                await websocket.send_json({
                    "type": "error",
                    "content": f"API 调用失败: {error_text}"
                })
    
    except WebSocketDisconnect:
        manager.disconnect_chat(websocket)
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        manager.disconnect_chat(websocket)


@router.websocket("/ws/flow")
async def flow_websocket(websocket: WebSocket):
    """
    工作流 WebSocket 端点
    
    消息格式:
    - 客户端: {"type": "subscribe"} - 订阅更新
    - 客户端: {"type": "add_task", "name": "任务名", "description": "描述"}
    - 客户端: {"type": "update_task", "index": 0, "status": "running"}
    - 客户端: {"type": "pop_task"} - 完成任务
    - 客户端: {"type": "clear"} - 清空
    - 服务端: {"type": "state", "data": {...}}
    """
    await manager.connect_flow(websocket)
    
    try:
        # 发送初始状态
        await websocket.send_json({
            "type": "state",
            "data": workflow_state.get_state()
        })
        
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            
            if msg_type == "subscribe":
                await websocket.send_json({
                    "type": "state",
                    "data": workflow_state.get_state()
                })
            
            elif msg_type == "add_task":
                name = data.get("name", "未命名任务")
                description = data.get("description", "")
                task = workflow_state.add_task(name, description)
                
                await manager.broadcast_flow({
                    "type": "task_added",
                    "data": task,
                    "state": workflow_state.get_state()
                })
            
            elif msg_type == "update_task":
                index = data.get("index", -1)
                status = data.get("status", "running")
                task = workflow_state.update_task_status(index, status)
                
                if task:
                    await manager.broadcast_flow({
                        "type": "task_updated",
                        "data": task,
                        "index": index,
                        "state": workflow_state.get_state()
                    })
            
            elif msg_type == "pop_task":
                task = workflow_state.pop_task()
                if task:
                    await manager.broadcast_flow({
                        "type": "task_completed",
                        "data": task,
                        "state": workflow_state.get_state()
                    })
            
            elif msg_type == "clear":
                workflow_state.clear()
                await manager.broadcast_flow({
                    "type": "state",
                    "data": workflow_state.get_state()
                })
    
    except WebSocketDisconnect:
        manager.disconnect_flow(websocket)
    except Exception as e:
        logger.error(f"Flow WebSocket error: {e}")
        manager.disconnect_flow(websocket)


# ==================== 辅助函数 ====================

async def broadcast_event(event_type: str, payload: dict, trace_id: str):
    """广播 Agent 事件"""
    event_data = {
        "event_type": event_type,
        "payload": payload,
        "trace_id": trace_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast_event(event_data)


async def notify_workflow_update(event_type: str, data: dict):
    """通知工作流更新（供 Agent 等模块调用）"""
    await manager.broadcast_flow({
        "type": event_type,
        "data": data,
        "state": workflow_state.get_state()
    })


def get_workflow_manager():
    """获取工作流状态管理器"""
    return workflow_state


def get_connection_manager():
    """获取连接管理器"""
    return manager


def get_chat_session():
    """获取聊天会话"""
    return None
