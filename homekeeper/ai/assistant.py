import os
import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


_PROCESS_REQUEST_TOOL = {
    "name": "process_request",
    "description": "Phân tích yêu cầu bảo trì nhà và trả về intent có cấu trúc",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["create_task", "find_repairman", "general"],
                "description": "Intent của tin nhắn người dùng",
            },
            "task_name": {
                "type": "string",
                "description": "Tên công việc bảo trì (chỉ dùng cho create_task)",
            },
            "cycle_days": {
                "type": "integer",
                "description": "Số ngày chu kỳ nhắc lại (chỉ dùng cho create_task, mặc định 30)",
            },
            "problem_description": {
                "type": "string",
                "description": "Mô tả sự cố của người dùng (chỉ dùng cho find_repairman)",
            },
            "suggested_service_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Loại dịch vụ phù hợp để tìm thợ "
                    "(ví dụ: ['điện', 'nước', 'máy lạnh', 'sơn', 'mộc'])"
                ),
            },
            "answer": {
                "type": "string",
                "description": "Câu trả lời cho câu hỏi chung (chỉ dùng cho general)",
            },
        },
        "required": ["intent"],
    },
}

_SYSTEM_PROMPT = (
    "Bạn là HomeKeeper AI, trợ lý quản lý nhà cửa thông minh.\n"
    "Phân tích tin nhắn và gọi tool process_request với intent phù hợp:\n\n"
    "- create_task: Người dùng muốn đặt lịch, nhắc nhở bảo trì định kỳ\n"
    "  (ví dụ: 'nhắc tôi thay bóng đèn sau 30 ngày', 'đặt lịch vệ sinh máy lạnh')\n"
    "  → Điền task_name và cycle_days (mặc định 30 nếu không rõ)\n\n"
    "- find_repairman: Người dùng mô tả sự cố hoặc cần tìm thợ\n"
    "  (ví dụ: 'điều hòa không mát', 'bồn cầu bị chảy nước', 'cần thợ điện')\n"
    "  → Điền problem_description và suggested_service_types\n\n"
    "- general: Câu hỏi chung về bảo trì, vận hành nhà cửa\n"
    "  → Điền answer bằng tiếng Việt, ngắn gọn và hữu ích"
)


def analyze_message(user_message: str) -> dict:
    """Return structured intent dict from user's natural-language message."""
    client = _get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[_PROCESS_REQUEST_TOOL],
        tool_choice={"type": "any"},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "process_request":
            return block.input
    return {
        "intent": "general",
        "answer": "Xin lỗi, tôi không hiểu yêu cầu. Bạn có thể mô tả rõ hơn không?",
    }
