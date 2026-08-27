# mimOE Local DevOps Troubleshooting Agent

A small Python command-line agent that sends DevOps questions to a model running locally in **mimOE Studio**. It uses the OpenAI Python SDK because mimOE exposes an OpenAI-compatible API.

This project intentionally has one application file. It demonstrates the required integration clearly without hiding the important behavior behind a framework.

## What it does

- Connects to whichever local model the user configures in `.env`
- Verifies the endpoint, API key, and model at startup
- Streams each response as it is generated
- Keeps multi-turn conversation history for the current session
- Uses a focused DevOps system prompt
- Supports `/clear` to reset context and `/exit` to quit
- Reads endpoint, key, model, and timeout from environment variables
- Gives practical messages for connection, authentication, and endpoint errors

## Architecture

```text
User in terminal
      |
      v
agent.py
  - loads configuration
  - keeps message history
  - prints streamed tokens
      |
      v
OpenAI Python SDK
      |
      |  POST /chat/completions
      v
mimOE OpenAI-compatible API
configured by MIMOE_BASE_URL
      |
      v
Active local model configured by MIMOE_MODEL
```

`agent.py` is the orchestration layer. It does not run an AI model itself. The OpenAI SDK formats requests and handles streaming; mimOE receives those requests and sends them to the locally loaded model.

## Prerequisites

- Python 3.10 or newer
- mimOE Studio running on the machine or reachable over the local network
- A chat-capable local model downloaded and shown as active in mimOE Studio
- The inference API enabled at the URL shown in mimOE Studio

## Configuration

The application does **not** contain a fixed IP address, port, key, or model name. It loads `.env` with `python-dotenv`, then `Config.from_environment()` reads these four environment variables:

| Variable | What to enter | Where to find it |
| --- | --- | --- |
| `MIMOE_BASE_URL` | Complete inference base URL | mimOE Studio API dialog |
| `MIMOE_API_KEY` | API key | mimOE Studio API dialog |
| `MIMOE_MODEL` | Exact active model identifier | mimOE Studio Model/API view |
| `MIMOE_TIMEOUT` | Request timeout in seconds | Optional; `60` is a reasonable default |

These values cannot all be discovered safely in a universal way. The program must know the address and key before it can contact mimOE, and a user may have more than one model available. For that reason, mimOE Studio's API dialog is the source of truth.

Two files keep configuration simple and safe:

- `.env.example` is a public template included in GitHub. It contains generic placeholders.
- `.env` is each user's private local configuration. Git ignores it, so it is not uploaded.

If mimOE and this CLI run on the same computer, `http://localhost:8083/mimik-ai/openai/v1` is the natural URL to try first. If mimOE Studio displays another address or port, use the displayed value instead. The traceable inference URL can also be used by assigning its complete value to `MIMOE_BASE_URL`; the Python code does not need to change.

## Setup

From the project directory, create and activate a virtual environment.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
```powershell
Copy-Item .env.example .env
```
```
Open `.env` and replace the three placeholder values with the exact Base URL, API Key, and Model shown by your mimOE Studio API dialog. Do not commit `.env`; it is ignored by Git.

Example private `.env` (illustrative values only):

```env
MIMOE_BASE_URL=http://localhost:8083/mimik-ai/openai/v1
MIMOE_API_KEY=your-key-from-mimoe
MIMOE_MODEL=your-active-model-id
MIMOE_TIMEOUT=60
```

## Run

Keep mimOE Studio open with the model named in `MIMOE_MODEL` active, then run:

```bash
python agent.py
```

At launch, the program sends a one-token test completion. This is more useful than only checking that the server responds: it verifies the base URL, API key, and selected model together. If it succeeds, the interactive prompt opens.

## Example interaction

```text
================================================
  mimOE Local DevOps Troubleshooting Agent
================================================
Endpoint: http://localhost:8083/mimik-ai/openai/v1
Model:    your-active-model-id
Checking connection... connected

Commands: /clear resets the conversation, /exit closes the agent.

You > My Kubernetes pod stays Pending. What should I check?

Agent > Start with `kubectl describe pod <pod-name>`. In the Events section,
look for insufficient CPU or memory, an unbound volume claim, node selector
mismatches, or missing tolerations.

You > Which of those relates to storage?

Agent > An unbound PersistentVolumeClaim. Check it with `kubectl get pvc` and
then describe the claim to see why it has not bound.

You > /clear
Conversation cleared.

You > /exit
Goodbye!
```

The exact wording and technical quality will vary because they depend on the selected local model. Small models may produce incorrect or unrelated answers; use an instruction-tuned model with enough capacity for the intended task when possible.

## How the code works

1. `Config.from_environment()` loads `.env`, checks the three required values, and validates the timeout.
2. `OpenAI(...)` points the standard SDK client at mimOE instead of OpenAI's hosted API.
3. `check_connection()` makes a minimal chat completion to test the whole path before entering the prompt loop.
4. `run_chat()` stores messages in a Python list. That list begins with a system prompt and is sent with every new question, which creates multi-turn memory.
5. `stream_answer()` requests `stream=True`, prints each arriving text fragment, and joins the fragments into the assistant message stored in history.
6. Failed questions are removed from history, so the conversation never contains a user question with no assistant response.

All memory is in RAM. Closing the process or using `/clear` removes it.

## Error handling

The program explains the most likely action for common failures:

- Cannot connect: verify mimOE is running, the model is active, and the IP/port is reachable.
- HTTP 401 or 403: verify `MIMOE_API_KEY`.
- HTTP 404: verify the base URL and loaded model name.
- Invalid local configuration: compare `.env` with `.env.example`.

If another computer runs this CLI, the mimOE host address and port must be reachable from it, and local firewall rules must allow the configured port.

## Design limitations

- The model is small and can produce incomplete or incorrect technical advice. Commands should be reviewed before use.
- Conversation history grows until `/clear` or exit and may eventually exceed the model's context window.
- History is not saved between runs.
- The agent suggests commands but deliberately does not execute them.
- There is no retrieval from private runbooks or documentation.
- The startup check creates a tiny inference request on every launch.
- The supplied local setup uses plain HTTP and a simple development key. A production deployment should use appropriate network protection and credentials.

These are conscious tradeoffs for a take-home project whose goal is a clear local-model integration.

## Repository contents

```text
.
|-- agent.py          # Complete CLI application
|-- requirements.txt  # Runtime dependencies
|-- .env.example      # Safe configuration template
|-- .gitignore        # Excludes secrets and generated files
`-- README.md         # Setup, design, and discussion
```
