"""JEV model integration module for Socratic conversation evaluation."""

import json
import logging
import os
from typing import Any, Dict, Optional, Tuple
import requests

logger = logging.getLogger("jev_pipeline")

DEFAULT_JEV_URL = os.getenv("JEV_URL", "http://127.0.0.1:8765/v1/systemone")
DEFAULT_PROVIDER = "imajev"
DEFAULT_MODEL_NAME = "imajev-2b"
DEFAULT_TIMEOUT_SECONDS = 300.0

FIXED_QUESTIONS: Dict[str, Any] = {
    "socratic_guidance": {
        "type": "score",
        "instructions": (
            "Evaluate the tutor's method of guidance across the entire conversation. "
            "Focus specifically on whether the tutor guides the student's reasoning primarily through questions "
            "that elicit thinking, or through statements that provide information, reasoning, or conclusions. "
            "Do not use the amount of help provided as the basis for this score."
        ),
        "criteria": [
            "Predominantly states answers, conclusions, or solution steps instead of eliciting student reasoning.",
            "Some questioning is present, but guidance is frequently statement-based, leading, or answer-revealing.",
            "Generally uses questions to guide the student's reasoning, with occasional direct statements or overly leading questions.",
            "Consistently uses targeted questions to elicit, probe, and extend the student's own reasoning.",
        ],
    },
    "scaffolding": {
        "type": "score",
        "instructions": (
            "Evaluate the granularity and amount of help provided by the tutor during each intervention across the conversation. "
            "Focus on how much reasoning or solution information the tutor supplies versus how much is left for the student to work out. "
            "Do not use whether the tutor asks a question or makes a statement as the basis for this score."
        ),
        "criteria": [
            "Provides essentially the complete solution or the key reasoning needed to solve the problem.",
            "Provides a large portion of the solution or reveals a major reasoning step.",
            "Provides a useful but limited direction while leaving meaningful reasoning to the student.",
            "Provides a small, targeted nudge that helps the student progress while leaving the central reasoning for them to discover.",
        ],
    },
    "state_adaptation": {
        "type": "score",
        "instructions": (
            "Evaluate how well the tutor responds to the student's current understanding, mistakes, confusion, and progress. "
            "Consider the relationship between each student response and the tutor's subsequent response."
        ),
        "criteria": [
            "Tutor responses are largely disconnected from the student's state.",
            "Tutor acknowledges the student's response but does not meaningfully adapt.",
            "Tutor generally adapts to the student's state but misses some important details.",
            "Tutor precisely responds to the student's current reasoning, misconception, or level of understanding.",
        ],
    },
    "diagnosis": {
        "type": "score",
        "instructions": (
            "Evaluate how well the tutor identifies and investigates what the student currently understands, misunderstands, or is unable to do. "
            "Assess the actual diagnostic behavior demonstrated, not the tutor's apparent intentions."
        ),
        "criteria": [
            "No meaningful diagnosis of the student's reasoning.",
            "Limited or inaccurate diagnosis.",
            "Generally identifies the relevant difficulty or understanding.",
            "Clearly identifies the student's reasoning state and uses appropriate questions to uncover it."
        ],
    },
    "student_agency": {
        "type": "score",
        "instructions": (
            "Evaluate who performs the intellectual heavy lifting throughout the conversation. "
            "Focus on whether the student generates, connects, tests, and articulates the important reasoning. "
            "Do not use the number of tutor questions as the basis for this score."
        ),
        "criteria": [
            "The tutor performs most of the important reasoning; the student mainly follows or confirms it.",
            "The student contributes some reasoning, but the tutor performs or supplies many important reasoning steps.",
            "The student performs a substantial portion of the reasoning, with the tutor providing meaningful support.",
            "The student performs the central reasoning, makes important connections, and articulates the solution or understanding in their own words.",
        ],
    },
    "progression": {
        "type": "score",
        "instructions": (
            "Evaluate whether the conversation moves the student meaningfully toward understanding and solving the problem. "
            "Consider the initial response, intermediate reasoning, corrections, and final demonstrated understanding."
        ),
        "criteria": [
            "Little or no meaningful progress.",
            "Some progress, but important confusion or gaps remain.",
            "Student makes substantial progress toward a correct solution or understanding.",
            "Student reaches the correct solution and demonstrates meaningful understanding of the underlying reasoning or principle.",
        ],
    },
    "coherence": {
        "type": "score",
        "instructions": (
            "Evaluate the logical and conversational consistency of the dialogue as a whole. "
            "Consider whether the tutor's responses form a connected progression that appropriately follows the student's responses."
        ),
        "criteria": [
            "Conversation is substantially incoherent or contradictory.",
            "Noticeable inconsistencies, repetition, or disconnected responses.",
            "Generally coherent with minor issues.",
            "Responses form a clear, logically connected progression throughout.",
        ],
    },
}


def format_conversation_state(record: Dict[str, Any]) -> Dict[str, Any]:
    """Format an input dataset conversation record into the state dictionary expected by JEV."""
    domain = str(record.get("domain", "") or "")
    topic = str(record.get("topic", "") or "")
    problem = str(record.get("problem", "") or "")
    raw_conv = record.get("conversation", [])
    if not isinstance(raw_conv, list):
        raw_conv = []

    formatted_turns = []
    for idx, turn in enumerate(raw_conv):
        if not isinstance(turn, dict):
            continue
        turn_num = turn.get("turn", idx + 1)
        speaker = str(turn.get("speaker", "") or "")
        # Student turns usually contain 'text'; tutor turns in generated datasets have 'response'
        text = str(turn.get("text") or turn.get("response") or turn.get("content") or "")
        formatted_turns.append(
            {
                "turn": turn_num,
                "speaker": speaker,
                "text": text,
            }
        )

    return {
        "domain": domain,
        "topic": topic,
        "problem": problem,
        "conversation": formatted_turns,
    }


def call_jev(
    state: Dict[str, Any],
    questions: Optional[Dict[str, Any]] = None,
    url: str = DEFAULT_JEV_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Tuple[bool, Optional[Dict[str, Any]], int, Optional[str]]:
    """
    Call the JEV evaluation model endpoint.

    Returns:
        (success, response_dict, total_tokens, error_code)
    """
    payload = {
        "state": state,
        "questions": questions if questions is not None else FIXED_QUESTIONS,
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        logger.error("JEV request timed out after %.1f seconds contacting %s", timeout, url)
        return False, None, 0, "TIMEOUT"
    except requests.exceptions.ConnectionError as exc:
        logger.error("JEV connection error contacting %s: %s", url, exc)
        return False, None, 0, "CONNECTION_ERROR"
    except requests.exceptions.RequestException as exc:
        logger.error("JEV request exception: %s", exc)
        return False, None, 0, "REQUEST_ERROR"
    except Exception as exc:
        logger.error("Unexpected error contacting JEV endpoint: %s", exc)
        return False, None, 0, "UNEXPECTED_ERROR"

    if response.status_code != 200:
        logger.error("JEV endpoint returned HTTP %s: %s", response.status_code, response.text[:500])
        return False, None, 0, f"HTTP_{response.status_code}"

    try:
        data = response.json()
    except Exception as exc:
        logger.error("Failed to parse JEV response JSON: %s", exc)
        return False, None, 0, "JSON_PARSE_ERROR"

    if not isinstance(data, dict):
        logger.error("JEV response is not a JSON object: %s", type(data))
        return False, None, 0, "INVALID_RESPONSE_TYPE"

    usage = data.get("usage", {})
    total_tokens = 0
    if isinstance(usage, dict):
        raw_tokens = usage.get("total_tokens") or usage.get("input_tokens") or 0
        try:
            total_tokens = int(raw_tokens)
        except (ValueError, TypeError):
            total_tokens = 0

    return True, data, total_tokens, None
