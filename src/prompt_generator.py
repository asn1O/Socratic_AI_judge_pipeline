from pathlib import Path
import json
from typing import Any, Optional, Tuple


class DatasetPromptGenerator:
    """Build the evaluation prompt from judge_prompt.md and inject a conversation JSON payload."""

    def __init__(self, template_path: Optional[str] = None):
        self.template_path = (
            Path(template_path)
            if template_path
            else Path(__file__).resolve().parent.parent / "judge_prompt.md"
        )

    @staticmethod
    def _serialize_conversation(conversation: Any) -> str:
        """Coerce a conversation object into a JSON string for prompt injection."""
        if conversation is None:
            return json.dumps({}, ensure_ascii=False, indent=2)
        if isinstance(conversation, str):
            try:
                return json.dumps(json.loads(conversation), ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                return conversation
        return json.dumps(conversation, ensure_ascii=False, indent=2)

    def generate_prompt(self, conversation: Any = None) -> Tuple[str, str]:
        """Return the populated judge prompt and the serialized conversation payload."""
        template = self.template_path.read_text(encoding="utf-8")
        conversation_json = self._serialize_conversation(conversation)

        template = template.replace("<<<CONVERSATION>>>", conversation_json)
        template = template.replace("<<CONVERSATION>>", conversation_json)

        return template, conversation_json


def main() -> None:
    """Example usage for direct prompt generation with a conversation object."""
    sample_conversation = {
        "conversation": [
            {"speaker": "student", "content": "I think the tutor should ask me something first."},
            {"speaker": "tutor", "content": "What do you think the key idea is here?"},
        ]
    }
    print(DatasetPromptGenerator().generate_prompt(sample_conversation)[0])


if __name__ == "__main__":
    main()
