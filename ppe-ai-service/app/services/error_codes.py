AI_INPUT_INVALID = "AI_400_INPUT_INVALID"
AI_NETWORK_RETRYABLE = "AI_502_NETWORK_RETRYABLE"
AI_RESOURCE_EXHAUSTED = "AI_503_RESOURCE_EXHAUSTED"
AI_MODEL_ERROR = "AI_500_MODEL_ERROR"
AI_TIMEOUT = "AI_504_TIMEOUT"


def map_exception_to_error(exc: Exception) -> tuple[str, str, bool]:
    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()
    if isinstance(exc, ValueError):
        return AI_INPUT_INVALID, message, False
    if "timeout" in lowered or "超时" in message:
        return AI_TIMEOUT, message, True
    if "connect" in lowered or "network" in lowered or "连接" in message:
        return AI_NETWORK_RETRYABLE, message, True
    if "memory" in lowered or "显存" in message or "resource" in lowered:
        return AI_RESOURCE_EXHAUSTED, message, True
    return AI_MODEL_ERROR, message, False
