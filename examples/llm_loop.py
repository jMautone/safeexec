"""LLM -> SafeExec -> correct: the loop this service exists to make safe.

Claude writes a program, SafeExec runs it inside a single-use container, and any
failure (crash, timeout, OOM) comes back as *data* so the model can fix its own
code and try again. Nothing the model writes ever touches this process.

    # real Claude, needs ANTHROPIC_API_KEY (or `ant auth login`)
    uv run --group examples python examples/llm_loop.py \
        "cual fue el crecimiento mes a mes de estas ventas"

    # scripted author: same loop, no API key, shows a deliberate failure + fix
    uv run --group examples python examples/llm_loop.py --offline

Both modes need SafeExec running (`docker compose up --build -d`).
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import uuid
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

import httpx

try:
    import anthropic
except ModuleNotFoundError:  # --offline does not need the SDK
    anthropic = None  # type: ignore[assignment]

MODEL = "claude-opus-5"
MAX_ATTEMPTS = 3
SANDBOX_TIMEOUT_MS = 5_000
SANDBOX_MEMORY_MB = 256

SAMPLE_DATA = json.dumps({"ventas": [100, 250, 310, 290, 415]})
SAMPLE_TASK = "Calcula el crecimiento mes a mes en porcentaje y muestralo redondeado a 1 decimal."

SYSTEM_PROMPT = """\
You write short programs that run inside a locked-down, single-use container.

Hard constraints of that sandbox — code that ignores them will fail:
- No network access at all. No pip/npm install. Standard library only.
- Read-only filesystem except a small /tmp. Do not write files elsewhere.
- Input arrives on stdin. The answer must be printed to stdout.
- A few seconds of wall-clock and a few hundred MB of memory. No infinite loops.

Return the complete program every time, not a diff. No markdown fences.
"""

CODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "enum": ["python", "javascript"]},
        "code": {"type": "string", "description": "Complete program, no markdown fences."},
    },
    "required": ["language", "code"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """What SafeExec returns. Timeout/OOM are results here, not errors."""

    stdout: str
    stderr: str
    exit_code: int | None
    duration_ms: int
    timed_out: bool
    oom_killed: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ExecutionResult:
        return cls(
            stdout=payload["stdout"],
            stderr=payload["stderr"],
            exit_code=payload["exit_code"],
            duration_ms=payload["duration_ms"],
            timed_out=payload["timed_out"],
            oom_killed=payload["oom_killed"],
        )

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.oom_killed

    def as_feedback(self) -> str:
        """The failure, phrased so the model can act on it."""
        if self.timed_out:
            headline = f"The program was killed at the {SANDBOX_TIMEOUT_MS} ms wall-clock limit."
        elif self.oom_killed:
            headline = f"The program was OOM-killed at the {SANDBOX_MEMORY_MB} MB memory limit."
        else:
            headline = f"The program exited with code {self.exit_code}."
        return (
            f"{headline}\n\n"
            f"stderr:\n{self.stderr.strip() or '(empty)'}\n\n"
            f"stdout:\n{self.stdout.strip() or '(empty)'}\n\n"
            "Fix it and return the complete program again."
        )


class SafeExecClient:
    """Thin wrapper over POST /v1/executions."""

    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=30.0)

    def run(self, *, language: str, code: str, stdin: str, request_id: str) -> ExecutionResult:
        response = self._client.post(
            "/v1/executions",
            json={
                "language": language,
                "code": code,
                "stdin": stdin,
                # Distinct per attempt: reusing an id would replay the stored
                # result instead of running the corrected code.
                "client_request_id": request_id,
                "limits": {"timeout_ms": SANDBOX_TIMEOUT_MS, "memory_mb": SANDBOX_MEMORY_MB},
            },
        )
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after", "?")
            raise RuntimeError(f"SafeExec is at capacity; retry after {retry_after}s")
        response.raise_for_status()
        return ExecutionResult.from_payload(response.json())

    def close(self) -> None:
        self._client.close()


class CodeAuthor(Protocol):
    """Whatever writes the code. Claude in practice, a script in the demo."""

    def propose(self, prompt: str) -> tuple[str, str]:
        """Return (language, code) for this prompt, keeping its own history."""


class ClaudeAuthor:
    """Claude with structured output, so no parsing of prose or fences."""

    def __init__(self) -> None:
        if anthropic is None:
            raise SystemExit(
                "The anthropic SDK is not installed. Run with --group examples, or use --offline."
            )
        self._client = anthropic.Anthropic(max_retries=4)
        self._messages: list[Any] = []

    def propose(self, prompt: str) -> tuple[str, str]:
        self._messages.append({"role": "user", "content": prompt})
        try:
            response = self._client.beta.messages.create(
                model=MODEL,
                max_tokens=16_000,
                system=SYSTEM_PROMPT,
                messages=self._messages,
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": CODE_SCHEMA},
                },
                # Recover server-side if a safety classifier declines the request.
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
            )
        except (TypeError, anthropic.AuthenticationError) as exc:
            # The SDK resolves credentials from ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN
            # or an `ant auth login` profile; none of them were usable.
            raise SystemExit(
                f"Could not authenticate against the Claude API ({exc}).\n"
                "Set ANTHROPIC_API_KEY, run `ant auth login`, or use --offline."
            ) from exc
        if response.stop_reason == "refusal":
            raise SystemExit(f"Claude declined this request ({response.stop_details}).")
        # Echo the turn back verbatim (thinking blocks included) so the next
        # attempt sees the code it is being asked to fix.
        self._messages.append({"role": "assistant", "content": response.content})
        text = next(block.text for block in response.content if block.type == "text")
        payload = json.loads(text)
        return payload["language"], payload["code"]


class ScriptedAuthor:
    """A fake author that fails on purpose, then fixes itself. No API key needed."""

    _PROGRAMS: ClassVar[list[str]] = [
        # Attempt 1: crashes — treats the whole payload as the list.
        textwrap.dedent("""\
            import json, sys
            data = json.load(sys.stdin)
            ventas = data
            for prev, cur in zip(ventas, ventas[1:]):
                print(round((cur - prev) / prev * 100, 1))
        """),
        # Attempt 2: reads the right key.
        textwrap.dedent("""\
            import json, sys
            ventas = json.load(sys.stdin)["ventas"]
            for i, (prev, cur) in enumerate(zip(ventas, ventas[1:]), start=2):
                print(f"mes {i}: {round((cur - prev) / prev * 100, 1)}%")
        """),
    ]

    def __init__(self) -> None:
        self._attempt = 0

    def propose(self, prompt: str) -> tuple[str, str]:
        program = self._PROGRAMS[min(self._attempt, len(self._PROGRAMS) - 1)]
        self._attempt += 1
        return "python", program


def _initial_prompt(task: str, data: str) -> str:
    return f"Task: {task}\n\nThis exact text arrives on stdin:\n{data}"


def solve(
    *, task: str, data: str, author: CodeAuthor, sandbox: SafeExecClient, max_attempts: int
) -> int:
    """Run the loop. Returns a process exit code."""
    run_id = uuid.uuid4().hex[:12]
    prompt = _initial_prompt(task, data)

    for attempt in range(1, max_attempts + 1):
        print(f"\n=== attempt {attempt}/{max_attempts} ===")
        language, code = author.propose(prompt)
        print(f"--- proposed {language} ---\n{code.strip()}")

        result = sandbox.run(
            language=language,
            code=code,
            stdin=data,
            request_id=f"{run_id}-{attempt}",
        )

        if result.ok:
            print(f"--- ok in {result.duration_ms} ms ---")
            print(result.stdout.rstrip() or "(no output)")
            return 0

        prompt = result.as_feedback()
        print(f"--- failed in {result.duration_ms} ms ---")
        print(prompt)

    print(f"\nGave up after {max_attempts} attempts.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default=SAMPLE_TASK, help="what the program must do")
    parser.add_argument("--data", default=SAMPLE_DATA, help="text piped to the program's stdin")
    parser.add_argument("--url", default="http://localhost:8000", help="SafeExec base URL")
    parser.add_argument("--attempts", type=int, default=MAX_ATTEMPTS)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use the scripted author instead of Claude (no API key needed)",
    )
    args = parser.parse_args()

    author: CodeAuthor = ScriptedAuthor() if args.offline else ClaudeAuthor()
    sandbox = SafeExecClient(args.url)
    try:
        return solve(
            task=args.task,
            data=args.data,
            author=author,
            sandbox=sandbox,
            max_attempts=args.attempts,
        )
    except httpx.ConnectError:
        print(f"Cannot reach SafeExec at {args.url}. Is `docker compose up` running?")
        return 2
    finally:
        sandbox.close()


if __name__ == "__main__":
    sys.exit(main())
