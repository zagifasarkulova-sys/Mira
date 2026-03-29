import os
import logging
import httpx
from typing import List, Dict

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

DEFAULT_SYSTEM_PROMPT = """Ты — личный ИИ-ментор. Ты знаешь цели, планы, успехи и ошибки пользователя из его базы знаний.
Отвечай конкретно, опираясь на предоставленный контекст из базы знаний пользователя.
Если в контексте есть релевантная информация — используй её. Если нет — отвечай честно из общих знаний.
Говори на русском языке. Будь прямым и полезным."""


async def ask_ai(
    user_id: int,
    user_message: str,
    history: List[Dict],
    context: str = "",
    system_prompt: str = "",
) -> str:
    """Отправить запрос в Groq API"""
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY не настроен."

    base_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    if context:
        full_system = (
            f"{base_prompt}\n\n"
            f"=== КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ===\n{context}\n"
            f"=== КОНЕЦ КОНТЕКСТА ==="
        )
    else:
        full_system = base_prompt

    messages = [{"role": "system", "content": full_system}]

    for msg in history[-8:]:  # последние 8 сообщений
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama3-70b-8192",
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.7,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "⚠️ Ошибка при обращении к ИИ. Попробуй ещё раз."


async def generate_image(prompt: str) -> str | None:
    """Генерация изображения через Replicate (Flux)"""
    if not REPLICATE_API_TOKEN:
        return None

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # Создаём задание
            resp = await client.post(
                "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
                headers={
                    "Authorization": f"Token {REPLICATE_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"input": {"prompt": prompt, "num_outputs": 1}},
            )
            prediction = resp.json()
            prediction_id = prediction.get("id")
            if not prediction_id:
                return None

            # Ждём результат
            for _ in range(30):
                import asyncio
                await asyncio.sleep(3)
                poll = await client.get(
                    f"https://api.replicate.com/v1/predictions/{prediction_id}",
                    headers={"Authorization": f"Token {REPLICATE_API_TOKEN}"},
                )
                result = poll.json()
                status = result.get("status")
                if status == "succeeded":
                    output = result.get("output")
                    if output and len(output) > 0:
                        return output[0]
                elif status in ("failed", "canceled"):
                    return None

        return None
    except Exception as e:
        logger.error(f"Replicate error: {e}")
        return None


async def analyze_week_progress(
    goals: list,
    diary_entries: list,
    focus_stats: dict = None,
    system_prompt: str = "",
) -> str:
    """Анализ прогресса за неделю"""
    goals_text = "\n".join([f"- {g['text']}" for g in goals]) or "не заданы"
    diary_text = "\n".join([
        f"[{e['entry_type']}] {e['text']}" for e in diary_entries
    ]) or "записей нет"

    focus_text = ""
    if focus_stats:
        focus_text = (
            f"\nФокус-сессии: {focus_stats.get('sessions', 0)} сессий, "
            f"{focus_stats.get('minutes', 0)} минут"
        )

    prompt = (
        f"Проанализируй мой прогресс за неделю:\n\n"
        f"ЦЕЛИ:\n{goals_text}\n\n"
        f"ДНЕВНИК:\n{diary_text}"
        f"{focus_text}\n\n"
        f"Дай честную оценку: что хорошо, что плохо, что улучшить на следующей неделе."
    )

    return await ask_ai(0, prompt, [], system_prompt=system_prompt)
