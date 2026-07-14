import base64
import json
import os

from groq import Groq

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


_PROCESS_REQUEST_TOOL = {
    "type": "function",
    "function": {
        "name": "process_request",
        "description": "Phân tích yêu cầu bảo trì nhà và trả về intent có cấu trúc",
        "parameters": {
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


_PHOTO_PROMPT = (
    "Bạn là HomeKeeper AI. Người dùng gửi ảnh về một vấn đề trong nhà.\n"
    "Hãy phân tích ảnh và trả về JSON với cấu trúc sau:\n"
    "{\n"
    '  "problem": "<mô tả ngắn vấn đề bằng tiếng Việt>",\n'
    '  "severity": "low|medium|high",\n'
    '  "service_types": ["<loại thợ 1>", "<loại thợ 2>"],\n'
    '  "advice": "<lời khuyên xử lý tạm thời hoặc ghi chú>"\n'
    "}\n"
    "Chỉ trả về JSON, không thêm gì khác.\n"
    "service_types ví dụ: điện, nước, máy lạnh, sơn, mộc, khóa, kính, trần thạch cao, máy bơm."
)


def analyze_photo(photo_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Analyze a photo of a home problem and return structured assessment."""
    client = _get_client()
    b64 = base64.b64encode(photo_bytes).decode()
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    },
                    {"type": "text", "text": _PHOTO_PROMPT},
                ],
            }
        ],
    )
    text = response.choices[0].message.content or ""
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "problem": text[:200] if text else "Không nhận diện được vấn đề",
            "severity": "medium",
            "service_types": [],
            "advice": "",
        }


def analyze_message(user_message: str) -> dict:
    """Return structured intent dict from user's natural-language message."""
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=512,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        tools=[_PROCESS_REQUEST_TOOL],
        tool_choice="required",
    )
    message = response.choices[0].message
    if message.tool_calls:
        return json.loads(message.tool_calls[0].function.arguments)
    return {
        "intent": "general",
        "answer": "Xin lỗi, tôi không hiểu yêu cầu. Bạn có thể mô tả rõ hơn không?",
    }
