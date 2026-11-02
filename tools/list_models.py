from pathlib import Path

from dotenv import dotenv_values
from google import genai
from google.genai import errors, types


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def main() -> int:
    """List generation models without sending any CSV data."""

    settings = dotenv_values(PROJECT_FOLDER / ".env")
    api_key = (settings.get("GEMINI_API_KEY") or "").strip()

    if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
        print("NOT READY: add your API key to the .env file.")
        return 1

    model_names = []

    try:
        with genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000),
        ) as client:
            for model in client.models.list():
                actions = model.supported_actions or []

                if "generateContent" in actions and model.name:
                    model_names.append(model.name)

    except errors.APIError as error:
        print(f"FAILED: model listing returned status {error.code}.")
        return 1

    except Exception as error:
        print(f"FAILED: model listing raised {type(error).__name__}.")
        return 1

    if not model_names:
        print("No generation models were listed.")
        return 1

    print("SUCCESS: retrieved the generation model list.")

    for name in sorted(model_names):
        print(name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())