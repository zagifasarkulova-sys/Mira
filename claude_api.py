import os
import json
import httpx

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


async def generate_words(used_words: list[str]) -> list[dict]:
    """Generate 5 new B1-B2 English words via Claude API."""

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

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["content"][0]["text"].strip()
        words = json.loads(text)
        return words[:5]


async def generate_quiz_options(word: str, translation: str, all_words: list[dict]) -> list[str]:
    """Generate 3 wrong translation options for a quiz question."""
    correct = translation
    available = [w["translation"] for w in all_words if w["translation"] != correct]

    if len(available) >= 3:
        import random
        wrong = random.sample(available, 3)
    else:
        # Ask Claude for distractors
        prompt = f"""Give 3 wrong Russian translations for the English word "{word}" (correct answer is "{translation}").
They should look plausible but be clearly different from the correct answer.
Respond ONLY with JSON array of 3 strings: ["вариант1", "вариант2", "вариант3"]"""

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["content"][0]["text"].strip()
            wrong = json.loads(text)

    import random
    options = wrong[:3] + [correct]
    random.shuffle(options)
    return options
