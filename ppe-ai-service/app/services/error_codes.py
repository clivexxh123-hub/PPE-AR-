from pydantic import ValidationError


AI_INPUT_INVALID = "AI_400_INPUT_INVALID"
AI_NETWORK_RETRYABLE = "AI_502_NETWORK_RETRYABLE"
AI_RESOURCE_EXHAUSTED = "AI_503_RESOURCE_EXHAUSTED"
AI_TIMEOUT = "AI_504_TIMEOUT"
AI_MODEL_ERROR = "AI_500_MODEL_ERROR"
COMMON_INTERNAL = "COMMON_500_INTERNAL"


def map_exception_to_error(exc: Exception) -> tuple[str, str, bool]:
    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()
    if isinstance(exc, (ValueError, ValidationError)):
        return AI_INPUT_INVALID, message, False
    if "timeout" in lowered or "timed out" in lowered or "\u8d85\u65f6" in message:
        return AI_TIMEOUT, message, True
    if "connect" in lowered or "network" in lowered or "\u8fde\u63a5" in message:
        return AI_NETWORK_RETRYABLE, message, True
    if "memory" in lowered or "\u663e\u5b58" in message or "resource" in lowered:
        return AI_RESOURCE_EXHAUSTED, message, True
    if "internal" in lowered or "unexpected" in lowered:
        return COMMON_INTERNAL, message, False
    return AI_MODEL_ERROR, message, False
