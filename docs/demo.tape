# Regenerate the README GIF:  docker compose up --build -d && vhs docs/demo.tape
Output docs/demo.gif

Set Shell "bash"
Set FontSize 15
Set Width 1100
Set Height 760
Set Padding 20
Set TypingSpeed 35ms
Set Theme "Catppuccin Mocha"

Hide
Type "export PS1='$ ' && clear" Enter
Show

Type "# 1. Run code in a single-use container; an infinite loop is killed at the limit" Enter
Sleep 500ms
Type `curl -s localhost:8000/v1/executions -H 'content-type: application/json' -d '{"language":"python","code":"while True: pass","limits":{"timeout_ms":1500}}' | jq '{exit_code, timed_out, duration_ms}'` Enter
Sleep 4s

Type "# 2. An LLM loop: the crash comes back as data and the model fixes its code" Enter
Sleep 500ms
Type "uv run -q --group examples python examples/llm_loop.py --offline" Enter
Sleep 8s
