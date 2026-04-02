import os
import json
import httpx

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


async def _ask_gemini(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


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

    text = await _ask_gemini(prompt)
    # Strip markdown fences if present
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)[:5]


async def generate_quiz_options(word: str, translation: str, all_words: list[dict]) -> list[str]:
    correct = translation
    available = [w["translation"] for w in all_words if w["translation"] != correct]

    if len(available) >= 3:
        import random
        wrong = random.sample(available, 3)
    else:
        prompt = f"""Give 3 wrong Russian translations for the English word "{word}" (correct answer is "{translation}").
They should look plausible but be clearly different from the correct answer.
Respond ONLY with JSON array of 3 strings, no markdown: ["вариант1", "вариант2", "вариант3"]"""

        text = await _ask_gemini(prompt)
        text = text.replace("```json", "").replace("```", "").strip()
        wrong = json.loads(text)

    import random
    options = wrong[:3] + [correct]
    random.shuffle(options)
    return options
