import os
import json
import re
import random
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _extract_json(text: str) -> str:
    """Strip markdown code fences and return clean JSON string."""
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    return text


async def _ask_groq(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def generate_words(used_words: list[str]) -> list[dict]:
    used_str = ", ".join(used_words[-200:]) if used_words else "none"

    prompt = f"""Generate exactly 5 English words for a learner at B1-B2 level (Intermediate / Upper-Intermediate).

Word criteria:
- Verbs, adjectives, nouns or adverbs that appear frequently in real conversations, articles, or emails
- B1-B2 difficulty: not too simple (go, big, eat) and not too rare/academic (ameliorate, ubiquitous)
- Good examples: reluctant, negotiate, acknowledge, fulfil, adjust, persuade, significant, concern, whereas, nevertheless
- Mix different parts of speech across the 5 words
- NOT in this already-used list: {used_str}

For each word provide:
- word: the English word (base form)
- translation: Russian translation (short, 1-3 words)
- example: one natural English sentence using the word in context (B1-B2 level sentence)

Respond ONLY with a valid JSON array, no markdown, no extra text:
[
  {{"word": "reluctant", "translation": "неохотный, нежелающий", "example": "He was reluctant to share his opinion in front of everyone."}},
  ...
]"""

    text = await _ask_groq(prompt)
    try:
        return json.loads(_extract_json(text))[:5]
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq вернул невалидный JSON: {e}\nОтвет: {text[:200]}") from e


async def generate_quiz_options(word: str, translation: str, all_words: list[dict]) -> list[str]:
    correct = translation
    available = [w["translation"] for w in all_words if w["translation"] != correct]

    if len(available) >= 3:
        wrong = random.sample(available, 3)
    else:
        prompt = f"""Give 3 wrong Russian translations for the English word "{word}" (correct answer is "{translation}").
They should look plausible but be clearly different from the correct answer.
Respond ONLY with JSON array of 3 strings, no markdown: ["вариант1", "вариант2", "вариант3"]"""

        text = await _ask_groq(prompt)
        try:
            wrong = json.loads(_extract_json(text))
        except json.JSONDecodeError as e:
            raise ValueError(f"Groq вернул невалидный JSON для вариантов: {e}") from e

    options = wrong[:3] + [correct]
    random.shuffle(options)
    return options
