from pathlib import Path

from dotenv import dotenv_values
from google import genai
from google.genai import errors, types


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def check_connection() -> int:
    """Test Gemini without reading or sending any CSV files."""

    settings = dotenv_values(PROJECT_FOLDER / ".env")

    api_key = (settings.get("GEMINI_API_KEY") or "").strip()
    model_name = (settings.get("GEMINI_MODEL") or "").strip()

    if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
        print("NOT READY: add your Gemini API key to the .env file.")
        return 1

    if not model_name:
        print("NOT READY: add GEMINI_MODEL to the .env file.")
        return 1

    try:
        # Use a 90-second HTTP timeout and one attempt.
        with genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=90000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        ) as client:
            response = client.models.generate_content(
                model=model_name,
                contents=(
                    "Reply with exactly this text and nothing else: "
                    "CONNECTION_OK"
                ),
            )

            reply = (response.text or "").strip()

    except errors.APIError as error:
        message = str(
            error.message or "No error description returned."
        )
        safe_message = message.replace(api_key, "[REDACTED]")

        print(f"FAILED: Gemini API returned status {error.code}.")
        print(f"Details: {safe_message[:1500]}")
        return 1

    except Exception as error:
        print(
            "FAILED: connection test raised "
            f"{type(error).__name__}."
        )
        return 1

    if not reply:
        print("FAILED: Gemini returned no text.")
        return 1

    print("SUCCESS: Gemini connection worked.")
    print(f"Model: {model_name}")
    print(f"Gemini response: {reply}")

    return 0


if __name__ == "__main__":
    raise SystemExit(check_connection())