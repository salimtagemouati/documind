"""
Minimal standalone verification script for Google Gemini API Key via LiteLLM.
Tests both chat completion (gemini/gemini-2.0-flash) and text embedding (gemini/text-embedding-004).
"""
import asyncio
import os
import sys
import litellm


async def main():
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Usage: python verify_gemini_key.py <YOUR_API_KEY>")
        print("Or set GOOGLE_API_KEY / GEMINI_API_KEY environment variable.")
        sys.exit(1)

    print(f"Testing Gemini API Key ({api_key[:6]}...{api_key[-4:]})...")

    # 1. Test LiteLLM embedding
    try:
        print("1. Testing LiteLLM embedding ('gemini/text-embedding-004')...", end=" ", flush=True)
        embed_resp = await litellm.aembedding(
            model="gemini/text-embedding-004",
            input=["DocuMind retrieval test"],
            api_key=api_key,
        )
        vec = embed_resp.data[0]["embedding"]
        print(f"✓ Success! (vector dim={len(vec)})")
    except Exception as e:
        print(f"✗ Embedding failed: {e}")
        return False

    # 2. Test LiteLLM chat completion
    try:
        print("2. Testing LiteLLM chat completion ('gemini/gemini-2.0-flash')...", end=" ", flush=True)
        comp_resp = await litellm.acompletion(
            model="gemini/gemini-2.0-flash",
            messages=[{"role": "user", "content": "Respond with single word: OK"}],
            max_tokens=5,
            api_key=api_key,
        )
        ans = comp_resp.choices[0].message.content.strip()
        print(f"✓ Success! (response='{ans}')")
    except Exception as e:
        print(f"✗ Completion failed: {e}")
        return False

    print("\n✓ All checks passed! Key is active and authorized for Gemini 2.0 Flash + text-embedding-004.")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
