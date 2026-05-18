# renewal_agent

Local Python prototype for browser automation experiments using Playwright and Azure OpenAI.

This README is limited to project setup, configuration, and development notes. It does not document task-specific automation workflows.

## Requirements

- Python 3.11+ recommended
- Windows PowerShell or another shell that can activate a virtual environment
- An Azure OpenAI deployment configured for chat completions
- Playwright browser binaries for Firefox

## Project Layout

```text
renewal_agent/
|-- main.py
|-- requirements.txt
|-- .env.example
|-- .env
```

## Setup

1. Create and activate a virtual environment.
2. Install Python dependencies.
3. Install the Playwright Firefox browser.
4. Copy `.env.example` to `.env` and fill in the Azure OpenAI settings.

Example PowerShell commands:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install firefox
Copy-Item .env.example .env
```

## Configuration

The application reads configuration from `.env`.

Required values:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`

Optional values with defaults in the code:

- `AZURE_OPENAI_DEPLOYMENT` default: `gpt-4o`
- `AZURE_OPENAI_API_VERSION` default: `2025-01-01-preview`

Example `.env` template:

```dotenv
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

## Development Notes

- `main.py` is the current single-file entry point.
- The script loads environment variables with `python-dotenv`.
- Browser automation is implemented with Playwright's synchronous Python API.
- Azure OpenAI access is configured through the `openai` Python client using a deployment-scoped base URL.

## Verification

After setup, validate the environment with lightweight checks such as:

```powershell
python -m py_compile main.py
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(bool(os.getenv('AZURE_OPENAI_API_KEY')))"
```

## Dependencies

Current Python dependencies are listed in `requirements.txt`:

- `playwright`
- `openai`
- `python-dotenv`

## Notes

- Keep `.env` out of source control.
- If browser startup fails, rerun `playwright install firefox`.
- There is currently no test suite or packaging metadata in this repository.