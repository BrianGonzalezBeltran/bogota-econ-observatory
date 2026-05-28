"""
LLM-as-Judge for evaluating Observatory agent responses.

Uses a lightweight Groq model (8B) to score responses on 4 quality dimensions.
Designed to run independently — only requires `requests` and GROQ_API_KEY.

Scoring dimensions:
  - factual_accuracy (1-5): Are numbers and claims correct?
  - language_match (1-5): Did agent respond in the question's language?
  - completeness (1-5): Does the answer fully address the question?
  - data_grounding (1-5): Does the answer cite specific data points?
"""

import os
import json
import requests

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for an AI assistant that answers questions about Bogotá's economy using real data.

You will receive a user question, the agent's answer, the expected response language, and optionally a reference answer.

Score the agent's answer on these 4 dimensions using a 1-5 scale:

1. **factual_accuracy**: Are the numbers and claims plausible and internally consistent? If a reference answer is provided, does the agent's answer align with it?
   5 = Fully accurate and consistent
   3 = Partially accurate, some correct data
   1 = Incorrect numbers, contradictions, or fabricated data

2. **language_match**: Did the agent respond in the expected language?
   5 = Correct language throughout
   3 = Mostly correct but some mixing
   1 = Wrong language entirely

3. **completeness**: Does the answer address all parts of the question?
   5 = Complete answer covering all aspects asked
   3 = Partial answer, missing some aspects
   1 = Does not address the question

4. **data_grounding**: Does the answer cite specific numbers, percentages, or data points?
   5 = Rich in specific data (numbers, percentages, counts, periods)
   3 = Some numbers but vague in places
   1 = No data cited, purely generic response

Respond with ONLY a JSON object. No markdown fences, no preamble, no explanation outside the JSON:
{"factual_accuracy": N, "language_match": N, "completeness": N, "data_grounding": N, "reasoning": "one sentence explanation"}"""


def judge_response(
    question: str,
    answer: str,
    language: str,
    reference_answer: str = None,
    api_key: str = None,
    model: str = None,
) -> dict:
    """
    Evaluate an agent response using LLM-as-judge via Groq API.

    Args:
        question: The original user question.
        answer: The agent's response to evaluate.
        language: Expected response language ("es" or "en").
        reference_answer: Optional ground-truth answer for comparison.
        api_key: Groq API key (defaults to GROQ_API_KEY env var).
        model: Judge model (defaults to JUDGE_MODEL env var or llama-3.1-8b-instant).

    Returns:
        dict with scores (1-5) for each dimension plus reasoning.
    """
    api_key = api_key or os.getenv("GROQ_API_KEY")
    model = model or os.getenv("JUDGE_MODEL", "llama-3.1-8b-instant")

    if not api_key:
        return _error_result("GROQ_API_KEY not set")

    user_message = (
        f"Question: {question}\n"
        f"Agent's answer: {answer}\n"
        f"Expected language: {language}\n"
        f"Reference answer: {reference_answer or 'Not available'}"
    )

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0,
            },
            timeout=30,
        )
        resp.raise_for_status()

        text = resp.json()["choices"][0]["message"]["content"].strip()
        text = text.replace("```json", "").replace("```", "").strip()
        scores = json.loads(text)

        # Clamp scores to valid range
        for key in ["factual_accuracy", "language_match", "completeness", "data_grounding"]:
            if key in scores and scores[key] is not None:
                scores[key] = max(1, min(5, int(scores[key])))

        return scores

    except requests.exceptions.HTTPError as e:
        return _error_result(f"Groq API error: {e.response.status_code}")
    except json.JSONDecodeError:
        return _error_result(f"Judge returned invalid JSON: {text[:100]}")
    except Exception as e:
        return _error_result(str(e))


def _error_result(reason: str) -> dict:
    return {
        "factual_accuracy": None,
        "language_match": None,
        "completeness": None,
        "data_grounding": None,
        "reasoning": f"Judge error: {reason}",
    }
