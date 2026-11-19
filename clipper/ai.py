"""AI metadata generator for titles, captions, hashtags, and hooks.
Supports Google Gemini, OpenAI, Anthropic, Groq, Ollama, and local rule-based generation.
All metadata is derived strictly from real speech transcript words.
"""

import os
import re
import json
import socket
import logging
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set
import httpx
from .config import settings

logger = logging.getLogger("clipper.ai")

GEMINI_WORKING_MODELS = ["gemini-flash-lite-latest", "gemini-3.8-flash"]

def is_ollama_online(ollama_url: str) -> bool:
    """Fast check if Ollama server port is open without blocking pipeline."""
    try:
        parsed = urlparse(ollama_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
        with socket.create_connection((host, port), timeout=0.08):
            return True
    except OSError:
        return False

def make_title_unique(title: str, used_titles: Set[str], clip_rank: int) -> str:
    """Ensures title is completely unique within the session."""
    clean = title.strip().strip('"').strip("'")
    if not clean:
        clean = f"Highlight #{clip_rank}"

    candidate = clean
    if candidate in used_titles:
        modifiers = ["(Uncut)", "(Reaction)", "(Watch Till End)", "(Climax)", "(Exclusive)", "(Viral)"]
        mod = modifiers[(clip_rank - 1) % len(modifiers)]
        candidate = f"{clean} {mod}"

    counter = 2
    base = candidate
    while candidate in used_titles:
        candidate = f"{base} [Part {counter}]"
        counter += 1

    used_titles.add(candidate)
    return candidate

def extract_local_metadata(
    transcript_text: str,
    clip_rank: int = 1,
    used_titles: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Generates punchy, unique title, caption, and hashtags locally derived strictly from real speech."""
    if used_titles is None:
        used_titles = set()

    clean_text = transcript_text.strip()
    words = clean_text.split()
    if not words:
        raise ValueError("Cannot generate clip metadata: clip transcript contains no spoken words.")

    chosen_title = ""
    clauses = [
        c.strip()
        for c in re.split(r"[.!?,\n-]", clean_text)
        if 8 <= len(c.strip()) <= 60
    ]

    question_clauses = [c for c in clauses if any(c.lower().startswith(q) for q in ["what", "why", "how", "did", "wait", "look", "kya", "kyun", "kaise"])]
    if question_clauses:
        for c in question_clauses:
            t = c.title()
            if t not in used_titles:
                chosen_title = t
                break

    if not chosen_title and clauses:
        for c in clauses:
            t = c.title()
            if t not in used_titles:
                chosen_title = t
                break

    if not chosen_title:
        first_words = " ".join(words[:min(6, len(words))]).title()
        chosen_title = f"{first_words}..."

    unique_title = make_title_unique(chosen_title, used_titles, clip_rank)
    preview_text = clean_text[:160].strip()
    caption = f"{preview_text}... Watch till the end! #shorts #viral"

    default_tags = ["#shorts", "#viral", "#fyp", "#trending", "#clip"]
    content_tags = []
    cleaned_words = [re.sub(r"[^\w]", "", w).lower() for w in words]
    stop_words = {
        "the", "and", "this", "that", "with", "have", "from", "they", "will", "would",
        "there", "their", "what", "about", "which", "when", "make", "like", "time",
        "just", "know", "take", "people", "into", "year", "your", "good", "some",
        "could", "them", "see", "other", "than", "then", "now", "look", "only",
        "come", "its", "over", "think", "also", "back", "after", "use", "two", "how",
        "work", "first", "well", "way", "even", "new", "want", "because", "any", "hai",
        "hain", "nahi", "kuch", "apne", "wale", "karein", "bhai"
    }
    for w in cleaned_words:
        if len(w) > 3 and w not in stop_words and f"#{w}" not in content_tags:
            content_tags.append(f"#{w}")
        if len(content_tags) >= 4:
            break

    hashtags = default_tags + content_tags

    return {
        "title": unique_title,
        "caption": caption,
        "hashtags": hashtags[:7],
        "provider": "local_fallback",
    }

# Backward compatibility alias
extract_fallback_metadata = extract_local_metadata

def generate_with_gemini(
    transcript_text: str,
    api_key: str,
    clip_rank: int = 1,
    used_titles: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Calls Google Gemini API with timeout and retry."""
    if not api_key:
        return None
    if used_titles is None:
        used_titles = set()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    prompt = f"""You are an elite short-form video producer.
Analyze this clip transcript and produce high-CTR metadata in valid JSON.
CRITICAL LANGUAGE REQUIREMENT: Write the title and caption in the EXACT SAME LANGUAGE and DIALECT as the transcript (e.g. Hindi, Hinglish, Spanish, English). Never translate or invent unrelated English phrases.
Transcript: "{transcript_text[:1200]}"

Return ONLY a raw JSON object with keys:
- "title": unique click-worthy hook title under 55 chars (no quotes)
- "caption": engaging description under 150 chars with a call to action
- "hashtags": array of 5 to 7 high-impact hashtags starting with #
"""
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 300},
    }

    for attempt in range(2):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                logger.info(f"Gemini API request status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    text_resp = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    logger.info(f"Gemini raw response: {text_resp}")
                    clean_json = re.sub(r"^```(?:json)?\s*|```\s*$", "", text_resp, flags=re.MULTILINE).strip()
                    parsed = json.loads(clean_json)
                    raw_title = str(parsed.get("title", f"Highlight #{clip_rank}"))
                    final_title = make_title_unique(raw_title, used_titles, clip_rank)
                    logger.info(f"Generated metadata via Gemini for clip #{clip_rank}")
                    return {
                        "title": final_title,
                        "caption": str(parsed.get("caption", "Watch this clip!")),
                        "hashtags": list(parsed.get("hashtags", ["#shorts", "#fyp"])),
                        "provider": "gemini",
                    }
                else:
                    logger.error(f"Gemini API error (HTTP {resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Gemini attempt {attempt + 1} exception: {e}")
    return None

def generate_with_openai(
    transcript_text: str,
    api_key: str,
    clip_rank: int = 1,
    used_titles: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Calls OpenAI API (gpt-4o-mini / gpt-3.5-turbo) with timeout and retry."""
    if not api_key:
        return None
    if used_titles is None:
        used_titles = set()

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prompt = f"""Analyze this video clip transcript and produce viral metadata in JSON.
CRITICAL LANGUAGE REQUIREMENT: Write the title and caption in the EXACT SAME LANGUAGE and DIALECT as the transcript (e.g. Hindi, Hinglish, Spanish, English). Never translate or invent unrelated English phrases.
Transcript: "{transcript_text[:1200]}"

Return ONLY JSON with keys:
- "title": hook title under 55 chars
- "caption": short description under 150 chars with CTA
- "hashtags": array of 5-7 hashtags starting with #
"""
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a professional social video producer. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 250,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(2):
        try:
            with httpx.Client(timeout=6.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    raw_title = str(parsed.get("title", f"Highlight #{clip_rank}"))
                    final_title = make_title_unique(raw_title, used_titles, clip_rank)
                    logger.info(f"Generated metadata via OpenAI for clip #{clip_rank}")
                    return {
                        "title": final_title,
                        "caption": str(parsed.get("caption", "Watch this clip!")),
                        "hashtags": list(parsed.get("hashtags", ["#shorts", "#fyp"])),
                        "provider": "openai",
                    }
                else:
                    logger.warning(f"OpenAI API status {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"OpenAI attempt {attempt + 1} error: {e}")
    return None

def generate_with_groq(
    transcript_text: str,
    api_key: str,
    clip_rank: int = 1,
    used_titles: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Calls Groq API (llama-3.1-8b-instant) with ultra-fast latency."""
    if not api_key:
        return None
    if used_titles is None:
        used_titles = set()

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You are a viral shorts editor. Output JSON with 'title', 'caption', 'hashtags'."},
            {"role": "user", "content": f'Transcript: "{transcript_text[:1200]}"'},
        ],
        "temperature": 0.7,
        "max_tokens": 250,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                parsed = json.loads(data["choices"][0]["message"]["content"])
                final_title = make_title_unique(str(parsed.get("title", f"Clip #{clip_rank}")), used_titles, clip_rank)
                return {
                    "title": final_title,
                    "caption": str(parsed.get("caption", "")),
                    "hashtags": list(parsed.get("hashtags", ["#shorts"])),
                    "provider": "groq",
                }
    except Exception as e:
        logger.warning(f"Groq API error: {e}")
    return None

def generate_with_ollama(
    transcript_text: str,
    ollama_url: str,
    clip_rank: int = 1,
    used_titles: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Calls local Ollama instance for metadata generation if running."""
    if not is_ollama_online(ollama_url):
        return None
    if used_titles is None:
        used_titles = set()

    endpoint = f"{ollama_url.rstrip('/')}/api/generate"
    prompt = f"""Transcript: "{transcript_text[:1000]}"
Return ONLY JSON with "title" (under 55 chars), "caption" (under 150 chars), and "hashtags" (list of strings)."""
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    try:
        timeout = httpx.Timeout(connect=0.3, read=3.5, write=1.0, pool=0.5)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(endpoint, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                parsed = json.loads(data.get("response", "{}"))
                if "title" in parsed:
                    final_title = make_title_unique(str(parsed.get("title")), used_titles, clip_rank)
                    return {
                        "title": final_title,
                        "caption": str(parsed.get("caption")),
                        "hashtags": list(parsed.get("hashtags", ["#shorts"])),
                        "provider": "ollama",
                    }
    except Exception:
        pass
    return None

def generate_clip_metadata(
    transcript_text: str,
    clip_rank: int = 1,
    used_titles: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Generates metadata trying configured provider -> fallback, NEVER hanging."""
    if used_titles is None:
        used_titles = set()

    provider = settings.llm_provider.lower() if hasattr(settings, "llm_provider") else "auto"

    # 1. Try selected provider
    if provider == "gemini" or (provider in ("auto", "") and settings.gemini_api_key):
        res = generate_with_gemini(transcript_text, settings.gemini_api_key, clip_rank, used_titles)
        if res:
            return res

    if provider == "openai" or (provider in ("auto", "") and settings.openai_api_key):
        res = generate_with_openai(transcript_text, settings.openai_api_key, clip_rank, used_titles)
        if res:
            return res

    if provider == "groq" or (provider in ("auto", "") and getattr(settings, "groq_api_key", "")):
        res = generate_with_groq(transcript_text, settings.groq_api_key, clip_rank, used_titles)
        if res:
            return res

    # 2. Try Ollama if configured
    if settings.ollama_url and is_ollama_online(settings.ollama_url):
        res = generate_with_ollama(transcript_text, settings.ollama_url, clip_rank, used_titles)
        if res:
            return res

    # 3. Always instant, reliable local fallback
    return extract_fallback_metadata(transcript_text, clip_rank, used_titles)

def generate_hook_alternatives(transcript_text: str, current_title: str) -> List[Dict[str, str]]:
    """Generates 3 punchy hook alternatives derived directly from the spoken words and language."""
    clean_text = transcript_text.strip()
    words = clean_text.split()

    # Extract meaningful clauses from the actual spoken transcript (B.4 language preservation)
    clauses = [
        c.strip()
        for c in re.split(r"[.!?,\n-]", clean_text)
        if len(c.strip()) >= 8
    ]

    # 1. Curiosity Hook: drawn directly from first spoken phrase
    if clauses:
        first_phrase = clauses[0].upper()[:40]
        curiosity = f"{first_phrase}?!"
    elif words:
        curiosity = f"{' '.join(words[:6]).upper()}?!"
    else:
        curiosity = f"{current_title.upper()[:40]}?!"

    # 2. Shock / Intense Hook: drawn from substantial spoken clause
    if len(clauses) > 1:
        second_phrase = max(clauses[1:], key=len).upper()[:40]
        shock = f"{second_phrase}!"
    elif clauses:
        shock = f"{clauses[0].upper()[:40]}!"
    else:
        shock = f"LOOK: {current_title.upper()[:35]}!"

    # 3. Question Hook: formed in the same language as the transcript
    if len(clauses) > 2:
        third_phrase = clauses[2].upper()[:38]
        question = f"{third_phrase}?"
    elif clauses:
        question = f"{clauses[-1].upper()[:38]}?"
    else:
        question = f"{current_title.upper()[:38]}?"

    # Try Gemini/OpenAI if available with strict language preservation
    if settings.gemini_api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
            prompt = f"""Generate exactly 3 viral TikTok hook overlay titles (under 40 characters each) for this video transcript.
CRITICAL LANGUAGE REQUIREMENT: You MUST write the hooks in the EXACT SAME LANGUAGE and DIALECT as the transcript (e.g. Hindi, Hinglish, Spanish, English). Never translate or invent unrelated English hooks.

Transcript:
"{clean_text[:600]}"

Return ONLY a JSON array with 3 objects, each having:
- "angle": ("Curiosity", "Shock", or "Question")
- "text": punchy short uppercase hook text
"""
            with httpx.Client(timeout=4.0) as client:
                resp = client.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.8, "maxOutputTokens": 200}
                })
                if resp.status_code == 200:
                    text_resp = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    clean_json = re.sub(r"^```json\s*|```\s*$", "", text_resp, flags=re.MULTILINE).strip()
                    parsed = json.loads(clean_json)
                    if isinstance(parsed, list) and len(parsed) >= 3:
                        return parsed[:3]
        except Exception:
            pass

    return [
        {"angle": "Curiosity", "text": curiosity.upper()[:45]},
        {"angle": "Shock", "text": shock.upper()[:45]},
        {"angle": "Question", "text": question.upper()[:45]},
    ]
