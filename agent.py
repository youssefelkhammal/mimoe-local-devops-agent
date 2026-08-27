"""A small DevOps troubleshooting CLI powered by a local mimOE model."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, OpenAIError


SYSTEM_PROMPT = """You are a concise DevOps troubleshooting assistant.
Help diagnose infrastructure, Linux, Docker, Kubernetes, CI/CD, and networking issues.
Ask for missing details when needed. Give the safest checks first, explain commands briefly,
and never claim that you ran a command or inspected a system yourself.
"""


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    model: str
    timeout: float

    @classmethod
    def from_environment(cls) -> "Config":
        """Load and validate configuration from .env and the process environment."""
        load_dotenv()

        base_url = os.getenv("MIMOE_BASE_URL", "").strip().rstrip("/")
        api_key = os.getenv("MIMOE_API_KEY", "").strip()
        model = os.getenv("MIMOE_MODEL", "").strip()

        missing = [
            name
            for name, value in (
                ("MIMOE_BASE_URL", base_url),
                ("MIMOE_API_KEY", api_key),
                ("MIMOE_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required setting(s): {', '.join(missing)}")

        placeholders = [
            name
            for name, value in (
                ("MIMOE_API_KEY", api_key),
                ("MIMOE_MODEL", model),
            )
            if value.lower().startswith("replace-with-")
        ]
        if placeholders:
            raise ValueError(
                "Replace the example value(s) in .env for: "
                f"{', '.join(placeholders)}"
            )

        try:
            timeout = float(os.getenv("MIMOE_TIMEOUT", "60"))
        except ValueError as exc:
            raise ValueError("MIMOE_TIMEOUT must be a number of seconds.") from exc

        if timeout <= 0:
            raise ValueError("MIMOE_TIMEOUT must be greater than zero.")

        return cls(base_url=base_url, api_key=api_key, model=model, timeout=timeout)


def friendly_error(exc: Exception, config: Config) -> str:
    """Turn SDK exceptions into useful messages for a local mimOE setup."""
    if isinstance(exc, APIConnectionError):
        return (
            f"Could not connect to mimOE at {config.base_url}. "
            "Confirm that mimOE Studio is running, the model is active, and the URL is reachable."
        )
    if isinstance(exc, APIStatusError):
        if exc.status_code in {401, 403}:
            return "mimOE rejected the API key. Check MIMOE_API_KEY in your .env file."
        if exc.status_code == 404:
            return (
                "mimOE returned 404. Check MIMOE_BASE_URL and confirm that "
                f"the model '{config.model}' is loaded."
            )
        return f"mimOE returned HTTP {exc.status_code}: {exc.message}"
    return f"The request failed: {exc}"


def check_connection(client: OpenAI, config: Config) -> None:
    """Make a minimal completion to verify the endpoint, key, and model together."""
    client.chat.completions.create(
        model=config.model,
        messages=[{"role": "user", "content": "Reply with OK."}],
        max_tokens=1,
        stream=False,
    )


def stream_answer(client: OpenAI, config: Config, messages: list[dict[str, str]]) -> str:
    """Print a streamed answer as it arrives and return the complete text."""
    stream = client.chat.completions.create(
        model=config.model,
        messages=messages,
        stream=True,
    )

    parts: list[str] = []
    for chunk in stream:
        if not chunk.choices:
            continue
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
            parts.append(content)

    print()
    return "".join(parts)


def run_chat(client: OpenAI, config: Config) -> None:
    """Run the interactive, in-memory conversation loop."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("\nCommands: /clear resets the conversation, /exit closes the agent.\n")
    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

        if not user_input:
            continue
        if user_input.lower() in {"/exit", "exit", "quit"}:
            print("Goodbye!")
            return
        if user_input.lower() == "/clear":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("Conversation cleared.\n")
            continue

        messages.append({"role": "user", "content": user_input})
        print("\nAgent > ", end="", flush=True)
        try:
            answer = stream_answer(client, config, messages)
        except KeyboardInterrupt:
            print("\n\nGeneration stopped. Goodbye!")
            return
        except (OpenAIError, OSError) as exc:
            print(f"\nError: {friendly_error(exc, config)}\n")
            messages.pop()  # Do not remember a question that did not get an answer.
            continue

        messages.append({"role": "assistant", "content": answer})
        print()


def main() -> int:
    try:
        config = Config.from_environment()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        print("Copy .env.example to .env, then check its values.")
        return 1

    client = OpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout=config.timeout,
    )

    print("=" * 48)
    print("  mimOE Local DevOps Troubleshooting Agent")
    print("=" * 48)
    print(f"Endpoint: {config.base_url}")
    print(f"Model:    {config.model}")
    print("Checking connection...", end=" ", flush=True)

    try:
        check_connection(client, config)
    except (OpenAIError, OSError) as exc:
        print("failed")
        print(f"Error: {friendly_error(exc, config)}")
        return 1

    print("connected")
    run_chat(client, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
