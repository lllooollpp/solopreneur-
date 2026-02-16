"""
LLM Provider 异常类定义
统一的异常处理机制
"""


class LLMProviderError(Exception):
    """LLM提供者基础异常类"""
    def __init__(self, message: str, provider: str = None, model: str = None):
        self.message = message
        self.provider = provider
        self.model = model
        super().__init__(self.message)


class LLMAPIError(LLMProviderError):
    """LLM API调用失败异常"""
    def __init__(self, message: str, status_code: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code


class LLMAuthenticationError(LLMProviderError):
    """LLM认证失败异常"""
    pass


class LLMRateLimitError(LLMProviderError):
    """LLM速率限制异常"""
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class LLMTimeoutError(LLMProviderError):
    """LLM请求超时异常"""
    pass


class LLMInvalidResponseError(LLMProviderError):
    """LLM响应格式无效异常"""
    pass
