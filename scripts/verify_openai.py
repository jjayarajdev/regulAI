"""Verify the OpenAI key works and surface available models for Sentinel."""

from openai import OpenAI

from packages.config.settings import settings


def main() -> None:
    if not settings.openai_api_key:
        print("✗ No OPENAI_API_KEY in .env")
        return
    client = OpenAI(api_key=settings.openai_api_key)
    models = client.models.list()
    ids = sorted({m.id for m in models.data})
    print(f"✓ Key works. {len(ids)} models available.")
    print()
    interesting = [
        m for m in ids
        if any(p in m for p in ("gpt-5", "gpt-4.1", "gpt-4o", "o1", "o3", "o4"))
    ]
    print(f"Models suitable for Sentinel (top candidates):")
    for m in interesting[:30]:
        marker = " ← configured" if m == settings.openai_model else ""
        print(f"  {m}{marker}")


if __name__ == "__main__":
    main()
