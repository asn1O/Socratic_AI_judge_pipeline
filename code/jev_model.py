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
            "Evaluate the method of guidance used by the tutor. "
            "Focus specifically on whether the tutor guides the student's reasoning primarily through questions "
            "that elicit thinking, or through statements that provide information, reasoning, or conclusions. "
            "Do not use the amount of help provided as the basis for this score. Evaluate the method of guidance."
        ),
        "criteria": [
            "Almost all guidance is statements (answers, solution steps, corrections, explanations). Any questions are rhetorical or have the answer built into them.",
            "Some genuine questions, but statements or leading questions make up about half or more of the guidance. The tutor often asks a question and then answers it, or states the next step.",
            "Most guidance is genuine questions that require the student to think, but at least once the tutor states a step, fact, or conclusion the student could have worked out, or asks a clearly leading question.",
            "Essentially every substantive turn is a question that requires the student to generate reasoning, including at least one that asks the student to justify or test their own idea. The tutor never states a step or conclusion the student could have reached themselves.",
        ],
    },
    "scaffolding": {
        "type": "score",
        "instructions": (
            "Evaluate the granularity and amount of help provided by the tutor during each intervention. "
            "Focus on how much of the reasoning or solution is supplied versus how much is left for the student to work out. "
            "Do not use whether the tutor asks a question or makes a statement as the basis for this score. "
            "Evaluate the amount and granularity of assistance."
        ),
        "criteria": [
            "Provides the full solution, the final answer, or performs the central step for the student.",
            "Names the key method or sets up the problem, so the student's central decision is made for them. The student only carries it out.",
            "Gives a useful partial direction (points to a relevant concept, step, or part of the problem) and the student still makes the central inference, but the help is larger than needed or comes before the student has had a chance to try.",
            "Gives the smallest nudge that could work (e.g., redirecting attention to one detail), and escalates only if the student stays stuck. The central reasoning is left entirely to the student.",
        ],
    },
    "state_adaptation": {
        "type": "score",
        "instructions": (
            "Evaluate how well the tutor responds to the student's current understanding, mistakes, confusion, and progress."
        ),
        "criteria": [
            "Responses do not depend on what the student said. They follow a script, or repeat a move that already failed.",
            'Acknowledges the student\'s response ("good," "not quite") but the next move is generic and could be given in reply to any answer.',
            "Most replies address the student's specific error or step, but at least one important thing is missed: an error left unaddressed, a correct step not recognized, a failed approach repeated, or difficulty not adjusted.",
            "Every reply is tied to the student's specific words or reasoning, targets the exact misconception, changes approach when something fails, and adjusts pace to the student's level. No important error or signal is missed.",
        ],
    },
    "diagnosis": {
        "type": "score",
        "instructions": (
            "Evaluate how well the tutor identifies and investigates what the student currently understands, misunderstands, or is unable to do."
        ),
        "criteria": [
            "No attempt to find out what the student thinks. The tutor acts on assumptions.",
            'Only generic checks ("Do you understand?"), or the tutor\'s inference about the difficulty is wrong or unsupported, or the tutor tells the student what is wrong without asking about their reasoning.',
            "Accurately identifies the main difficulty from the student's answers, but does not confirm it by asking the student to explain, or does not distinguish a slip from a misconception.",
            "Asks targeted questions that bring out the student's reasoning, accurately identifies the cause (slip, misconception, or missing prerequisite), and confirms it before intervening.",
        ],
    },
    "student_agency": {
        "type": "score",
        "instructions": (
            "Evaluate who performs the intellectual heavy lifting throughout the conversation. "
            "Focus on whether the student is the person generating, connecting, testing, and articulating the important reasoning. "
            "Do not use the number of tutor questions as the basis for this score. "
            "Evaluate who actually performs the reasoning."
        ),
        "criteria": [
            'The tutor produces nearly all key reasoning. The student confirms, copies, or says "ok."',
            "The student produces some steps, but the tutor chooses the strategy or makes the central inference. Student turns are short or echo the tutor.",
            "The student produces most steps, including the strategy or the central inference, but the tutor supplies at least one important step, or the student's explanation depends on the tutor's wording.",
            "The student produces the central reasoning, makes connections on their own, self-corrects, and explains in their own words. The tutor supplies no key reasoning step.",
        ],
    },
    "progression": {
        "type": "score",
        "instructions": (
            "Evaluate whether the conversation moves the student meaningfully toward understanding and solving the problem."
        ),
        "criteria": [
            "No progress, or the student ends more confused than they started.",
            "Partial progress: some steps completed or a misconception partly addressed, but the solution is incomplete or a major gap remains at the end.",
            "The student reaches, or is one step from, a correct solution, or the main misconception is resolved, but there is no evidence they understand why (no explanation, check, or transfer), or it happened only with heavy tutor support.",
            "The student reaches the correct solution through their own reasoning and shows understanding: explains why it works, states the principle, or handles a check or variant.",
        ],
    },
    "coherence": {
        "type": "score",
        "instructions": (
            "Evaluate the logical and conversational consistency of the dialogue."
        ),
        "criteria": [
            "Frequently contradictory or off-topic. Replies are often unrelated to the previous turn.",
            "Noticeable problems: a contradiction, an unanswered student question, purposeless repetition, or an uncorrected tutor error that affects the dialogue.",
            "Mostly coherent, with one or two minor issues (slight redundancy, a brief tangent, a minor wording slip) that do not affect the logic.",
            "Every turn follows from the previous one. No contradictions, repetition, or ignored questions.",
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
