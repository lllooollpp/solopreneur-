"""
API 速率限制中间�?
防止滥用和DDoS攻击
"""
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    简单的速率限制中间�?
    基于IP地址进行限制
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = defaultdict(list)
        self.cleanup_interval = 60  # �?0秒清理一次过期记�?
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next):
        """处理请求并应用速率限制"""
        # 跳过健康检查端�?
        if request.url.path in ["/health", "/ready", "/"]:
            return await call_next(request)
        
        # 获取客户端IP
        client_ip = self._get_client_ip(request)
        
        # 检查速率限制
        current_time = time.time()
        
        # 定期清理过期记录
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_requests(current_time)
            self.last_cleanup = current_time
        
        # 获取此IP的请求历�?
        request_times = self.request_counts[client_ip]
        
        # 移除超过1分钟的请求记�?
        cutoff_time = current_time - 60
        request_times[:] = [t for t in request_times if t > cutoff_time]
        
        # 检查是否超过限�?
        if len(request_times) >= self.requests_per_minute:
            logger.warning(
                f"速率限制触发: IP {client_ip} 超过 {self.requests_per_minute} 请求/分钟"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "速率限制",
                    "message": f"请求过于频繁，请稍后再试",
                    "retry_after": 60
                }
            )
        
        # 记录本次请求
        request_times.append(current_time)
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加速率限制响应�?
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(request_times)
        )
        response.headers["X-RateLimit-Reset"] = str(int(current_time + 60))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP地址"""
        # 优先从代理头获取
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 回退到直接连接IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _cleanup_old_requests(self, current_time: float):
        """清理所有过期的请求记录"""
        cutoff_time = current_time - 60
        
        # 清理空列表和过期记录
        ips_to_remove = []
        for ip, times in self.request_counts.items():
            times[:] = [t for t in times if t > cutoff_time]
            if not times:
                ips_to_remove.append(ip)
        
        for ip in ips_to_remove:
            del self.request_counts[ip]
        
        if ips_to_remove:
            logger.debug(f"清理�?{len(ips_to_remove)} 个过期IP记录")
