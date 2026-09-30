from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
from pathlib import Path
from typing import Optional

REQUEST_TIMEOUT_SECONDS = 20 * 60


@dataclass
class Model:
    provider: str
    api_key: str
    model_name: str
    url: str
    rpd: int
    rpd_left: int
    tpd: Optional[int]
    tpd_left: Optional[int]
    last_use: Optional[datetime]
    expired: bool = False
    cooldown_until: Optional[datetime] = None
    tier: int = 0
    no_of_replies: int = 0
    avg_tokens_used: float = 0.0
    api_key_env: Optional[str] = None
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        Path(self.dest_write_path).mkdir(parents=True, exist_ok=True)

    @property
    def ok_to_use(self) -> bool:
        """Check whether the model still has usable quota."""

        if self.expired:
            return False

        tpd_ok = (self.tpd_left is None) or (self.tpd_left > 0)
        return (self.rpd_left > 0) and tpd_ok

    def mark_expired(self, now: Optional[datetime] = None) -> None:
        """Mark the model as temporarily unusable until its reset window expires."""
        self.expired = True
        if now is None:
            now = datetime.now(timezone.utc)
        self.last_use = now

    def reset_quota(self) -> None:
        """Reset rate-limit counters after the refresh window has elapsed."""
        self.rpd_left = self.rpd
        if self.tpd is not None:
            self.tpd_left = self.tpd
        self.expired = False
        self.last_use = None

    def increment_consecutive_failures(self) -> None:
        """Increment consecutive failure counter."""
        self.consecutive_failures += 1

    def reset_consecutive_failures(self) -> None:
        """Reset consecutive failure counter to 0."""
        self.consecutive_failures = 0

    def to_dict(self) -> dict:
        """Serialize Model to a JSON-serializable dictionary."""

        d = asdict(self)
        d["api_key"] = self.api_key_env or d["api_key"]
        d.pop("api_key_env", None)
        d["last_use"] = self.last_use.isoformat() if self.last_use else None
        d["cooldown_until"] = (
            self.cooldown_until.isoformat() if self.cooldown_until else None
        )
        return d

    @staticmethod
    def from_dict(d: dict) -> "Model":
        """Create a Model from a dictionary."""

        last = d.get("last_use")
        last_use = datetime.fromisoformat(last) if last else None
        if last_use is not None and last_use.tzinfo is None:
            last_use = last_use.replace(tzinfo=timezone.utc)

        cooldown = d.get("cooldown_until")
        cooldown_until = datetime.fromisoformat(cooldown) if cooldown else None
        if cooldown_until is not None and cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)

        raw_tpd = d.get("tpd")
        tpd = int(raw_tpd) if raw_tpd is not None else None

        raw_tpd_left = d.get("tpd_left")

        if raw_tpd_left is None:
            tpd_left = tpd
        else:
            tpd_left = int(raw_tpd_left)

        expired = bool(d.get("expired", False))
        api_key = os.getenv(d["api_key"], "")
        return Model(
            provider=d["provider"],
            api_key=api_key,
            model_name=d["model_name"],
            url=d["url"],
            rpd=int(d["rpd"]),
            rpd_left=int(d.get("rpd_left", d["rpd"])),
            tpd=tpd,
            tpd_left=tpd_left,
            last_use=last_use,
            expired=expired,
            cooldown_until=cooldown_until,
            tier=int(d.get("tier", 0)),
            no_of_replies=int(d.get("no_of_replies", 0)),
            avg_tokens_used=float(d.get("avg_tokens_used", 0.0) or 0.0),
            api_key_env=d["api_key"],
            consecutive_failures=int(d.get("consecutive_failures", 0)),
        )

    def record_response(self, total_tokens: Optional[int] = None) -> None:
        """Update response counters and running average token usage."""
        if total_tokens is None:
            total_tokens = 0

        previous_replies = self.no_of_replies
        self.no_of_replies = previous_replies + 1
        self.avg_tokens_used = (
            ((self.avg_tokens_used * previous_replies) + int(total_tokens))
            / self.no_of_replies
            if self.no_of_replies > 0
            else 0.0
        )

    @property
    def _response_file_stem(self) -> str:
        return f"{self.provider}_{self.model_name}".replace("/", "_")

    @property
    def dest_write_path(self) -> str:
        return str(Path("data") / self._response_file_stem)

    def write_response(self, response: dict) -> Path:
        """Append a response to the model's JSON set containing at most 15 items."""
        response_dir = Path(self.dest_write_path)
        contributor_id = os.getenv("DATASET_GENERATOR_ID", "").strip()
        if not contributor_id or not re.fullmatch(r"[A-Za-z0-9_-]+", contributor_id):
            raise ValueError(
                "DATASET_GENERATOR_ID must contain only letters, numbers, '-' or '_'."
            )

        set_files = []
        for path in response_dir.glob(f"{contributor_id}-set[[]*.json"):
            match = re.fullmatch(
                rf"{re.escape(contributor_id)}-set\[(\d+)\]\.json",
                path.name,
            )
            if match:
                set_files.append((int(match.group(1)), path))

        if set_files:
            set_index, response_path = max(set_files, key=lambda item: item[0])
            with response_path.open("r", encoding="utf-8") as file:
                responses = json.load(file)
            if not isinstance(responses, list):
                raise ValueError(f"Expected a JSON array in {response_path}")
        else:
            set_index = 0
            response_path = response_dir / f"{contributor_id}-set[{set_index}].json"
            responses = []

        if len(responses) >= 15:
            set_index += 1
            response_path = response_dir / f"{contributor_id}-set[{set_index}].json"
            if response_path.exists():
                with response_path.open("r", encoding="utf-8") as file:
                    responses = json.load(file)
                if not isinstance(responses, list):
                    raise ValueError(f"Expected a JSON array in {response_path}")
            else:
                responses = []

        responses.append(response)
        with response_path.open("w", encoding="utf-8") as file:
            json.dump(responses, file, indent=2, ensure_ascii=False)
            file.write("\n")

        return response_path

    def write_rejected_response(self, response: object) -> Path:
        """Append a rejected raw response to this model's text file."""
        rejected_dir = Path("data") / "rejected_responses"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        contributor_id = os.getenv("DATASET_GENERATOR_ID", "").strip()
        if not contributor_id or not re.fullmatch(r"[A-Za-z0-9_-]+", contributor_id):
            raise ValueError(
                "DATASET_GENERATOR_ID must contain only letters, numbers, '-' or '_'."
            )

        response_path = rejected_dir / f"{contributor_id}-{self._response_file_stem}.txt"
        response_text = (
            response
            if isinstance(response, str)
            else json.dumps(response, ensure_ascii=False, default=str)
        )

        with response_path.open("a", encoding="utf-8") as file:
            if response_path.stat().st_size > 0:
                file.write("\n\n")
            file.write(response_text)
            file.write("\n")

        return response_path

    def display_details(self):
        print(f"Provider: {self.provider}")
        print(f"Model: {self.model_name}")
        print(f"URL: {self.url}")
        print(f"RPD: {self.rpd}")
        print(f"RPD Left: {self.rpd_left}")
        print(f"TPD: {self.tpd}")
        print(f"TPD Left: {self.tpd_left}")
        print(f"Last Use: {self.last_use}")
        print(f"Tier: {self.tier}")
        print(f"Destination Write Path: {self.dest_write_path}")
        print(f"No. of Replies: {self.no_of_replies}")
        print(f"Average Tokens Used: {self.avg_tokens_used}")

    def test_connection(self) -> bool:
        """
        Test whether the model is reachable and returns usable text.

        Returns:
            True  -> request succeeded and model returned text
            False -> request failed or returned no usable text
        """

        success, _, _, _ = self.test_connection_with_reply()
        return success

    def test_connection_with_reply(self):
        """
        Test the model and return:

            (success, reply, total_tokens, error_code)

        Example:

            True, "yes", 12, None
            False, None, 0, "HTTP_404"
        """

        return self.call_model("Say only 'yes' or 'no'.")

    def test_socratic(self):
        """Generate a Socratic dataset prompt and send it to the model."""
        try:
            from .prompt_generator import DatasetPromptGenerator
        except ImportError:
            from prompt_generator import DatasetPromptGenerator

        prompt , metadata = DatasetPromptGenerator().generate_prompt()
        return self.call_model(prompt)

    def _set_rate_limit_cooldown(self, error: Exception) -> None:
        """Set a cooldown from Retry-After, falling back to 24 hours."""
        now = datetime.now(timezone.utc)
        retry_after = None
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)

        if headers is not None:
            retry_after = headers.get("retry-after")
            if retry_after is None:
                retry_after = headers.get("Retry-After")

        cooldown_until = None
        if retry_after is not None:
            try:
                cooldown_until = now + timedelta(seconds=max(float(retry_after), 0))
            except (TypeError, ValueError):
                try:
                    cooldown_until = parsedate_to_datetime(str(retry_after))
                    if cooldown_until.tzinfo is None:
                        cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError, OverflowError):
                    cooldown_until = None

        self.cooldown_until = cooldown_until or (now + timedelta(hours=24))

    def call_model(self, prompt: str):
        """
        Send a prompt to the model and return:

            (success, reply, total_tokens, error_code)
        """

        # Get provider hostname
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self.url or "")
            provider = parsed.netloc or self.url

        except Exception:
            provider = self.url

        # Import OpenAI SDK
        try:
            from openai import (
                OpenAI,
                APIError,
                APIConnectionError,
                APITimeoutError,
                RateLimitError,
                AuthenticationError,
                APIStatusError,
            )

        except Exception:
            print(
                f"[provider={provider} model={self.model_name}] "
                "OpenAI SDK is not available. "
                "Install it with 'pip install openai'."
            )
            return False, None, 0, "SDK_UNAVAILABLE"

        try:
            # Create client
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.url if self.url else None,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            # Make request
            self.last_use = datetime.now(timezone.utc)
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                # max_tokens=20,
            )

            # Extract actual LLM reply
            #
            # Chat Completions response:
            #
            # response
            #   └── choices[0]
            #          └── message
            #                 └── content
            #
            reply = response.choices[0].message.content
            total_tokens = response.usage.total_tokens if response.usage else None

            # Model was reachable but didn't return text
            if not reply:
                print(
                    f"[provider={provider} model={self.model_name}] "
                    "Model was reachable but returned no text."
                )
                return False, None, total_tokens, "NO_RESPONSE"

            # Success
            self.record_response(total_tokens)
            print(
                f"[provider={provider} model={self.model_name}] "
                "Success: received response — model appears reachable."
            )

            return True, reply, total_tokens, None

        # -------------------------
        # Rate limit
        # -------------------------

        except RateLimitError as error:
            self._set_rate_limit_cooldown(error)
            self.expired = True
            self.last_use = datetime.now(timezone.utc)
            print(
                f"[provider={provider} model={self.model_name}] "
                "Rate limited (429). "
                "Please check your quota and try again later."
            )
            return False, None, 0, "HTTP_429"

        # -------------------------
        # Authentication
        # -------------------------

        except AuthenticationError:
            print(
                f"[provider={provider} model={self.model_name}] "
                "Authentication error (401). "
                "Check API key and permissions."
            )
            return False, None, 0, "HTTP_401"

        # -------------------------
        # HTTP status errors
        # -------------------------

        except APIStatusError as e:

            if e.status_code == 404:
                print(
                    f"[provider={provider} model={self.model_name}] "
                    f"Not found (404): model '{self.model_name}' "
                    "was not found. Check the model name."
                )
                return False, None, 0, "HTTP_404"

            print(
                f"[provider={provider} model={self.model_name}] "
                f"HTTP {e.status_code}. "
                f"Response: {str(e)[:500]}"
            )

            return False, None, 0, f"HTTP_{e.status_code}"

        # -------------------------
        # Connection errors
        # -------------------------

        except APIConnectionError as e:
            self.expired = True
            self.last_use = datetime.now(timezone.utc)
            print(
                f"[provider={provider} model={self.model_name}] "
                f"Connection error when contacting {self.url}: {e}"
            )
            return False, None, 0, "API_CONNECTION_ERROR"

        except (TimeoutError, APITimeoutError):
            self.expired = True
            self.last_use = datetime.now(timezone.utc)
            print(
                f"[provider={provider} model={self.model_name}] "
                "Request timed out; marking model as expired."
            )
            return False, None, 0, "TIMEOUT"

        # -------------------------
        # Other OpenAI API errors
        # -------------------------

        except APIError as e:
            print(
                f"[provider={provider} model={self.model_name}] "
                f"API error: {e}"
            )
            return False, None, 0, "API_ERROR"

        # -------------------------
        # Anything unexpected
        # -------------------------

        except Exception as e:
            print(
                f"[provider={provider} model={self.model_name}] "
                f"Unexpected error when attempting request: {e}"
            )
            return False, None, 0, "UNEXPECTED_ERROR"