"""
Model verification script for Google Gemini via LiteLLM.
Tests candidate embedding and chat models against the configured API key.
"""
import asyncio
import os
import sys

import litellm

# Candidates to evaluate
EMBEDDING_CANDIDATES = [
    "gemini/gemini-embedding-001",
    "gemini/text-embedding-004",
]

CHAT_CANDIDATES = [
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.0-flash",
    "gemini/gemini-3.6-flash",
    "gemini/gemini-flash-latest",
]


async def test_embedding_model(model: str, api_key: str):
    try:
        # Test with dimensions=768 if supported (Matryoshka)
        resp = await litellm.aembedding(
            model=model,
            input=["DocuMind retrieval test passage"],
            dimensions=768,
            api_key=api_key,
        )
        vec = resp.data[0]["embedding"]
        dim = len(vec)
        print(f"  ✅ {model:<30} -> dim={dim}")
        return model, dim, True
    except Exception as e:
        err_str = str(e).replace(api_key, "[REDACTED]")[:120]
        # Try without dimensions parameter in case it's rejected
        try:
            resp = await litellm.aembedding(
                model=model,
                input=["DocuMind retrieval test passage"],
                api_key=api_key,
            )
            vec = resp.data[0]["embedding"]
            dim = len(vec)
            print(f"  ✅ {model:<30} -> dim={dim} (default dims)")
            return model, dim, True
        except Exception as e2:
            err2_str = str(e2).replace(api_key, "[REDACTED]")[:120]
            print(f"  ❌ {model:<30} -> {err2_str}")
            return model, 0, False


async def test_chat_model(model: str, api_key: str):
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "Respond with single word: OK"}],
            max_tokens=10,
            api_key=api_key,
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"  ✅ {model:<30} -> response='{content}'")
        return model, True
    except Exception as e:
        err_str = str(e).replace(api_key, "[REDACTED]")[:120]
        print(f"  ❌ {model:<30} -> {err_str}")
        return model, False


async def main():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: Missing GEMINI_API_KEY or GOOGLE_API_KEY environment variable.", file=sys.stderr)
        print("Please set GEMINI_API_KEY or GOOGLE_API_KEY before running this script.", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print("🔬 DocuMind Gemini Model Compatibility Test (via LiteLLM)")
    print("=" * 65)

    print("\n1. Testing Embedding Candidates:")
    embedding_results = []
    for model in EMBEDDING_CANDIDATES:
        res = await test_embedding_model(model, api_key)
        embedding_results.append(res)

    print("\n2. Testing Chat Candidates:")
    chat_results = []
    for model in CHAT_CANDIDATES:
        res = await test_chat_model(model, api_key)
        chat_results.append(res)

    print("\n" + "=" * 65)
    working_embeddings = [r for r in embedding_results if r[2]]
    working_chats = [r for r in chat_results if r[1]]

    if not working_embeddings or not working_chats:
        print(f"FAILED: Found {len(working_embeddings)} embedding and {len(working_chats)} chat models working.")
        sys.exit(1)

    print(f"SUCCESS: {len(working_embeddings)} embedding and {len(working_chats)} chat model(s) verified.")
    best_embed = working_embeddings[0]
    best_chat = working_chats[0]
    print(f"Recommended Configuration:")
    print(f"  EMBEDDING_MODEL = \"{best_embed[0]}\" (dim={best_embed[1]})")
    print(f"  LLM_MODEL       = \"{best_chat[0]}\"")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
