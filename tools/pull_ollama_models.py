import os
import sys
import time

import httpx

BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
# Default kept small for low-RAM environments.
MODELS = sys.argv[1:] or ["qwen2.5:0.5b", "nomic-embed-text"]


def pull_model(model: str) -> None:
    url = f"{BASE_URL}/api/pull"
    print(f"\n==> Pulling {model} from {url}")

    # Localhost over HTTP; disable SSL verification and env proxy handling.
    with httpx.Client(timeout=None, verify=False, trust_env=False) as client:
        with client.stream("POST", url, json={"name": model, "stream": True}) as resp:
            resp.raise_for_status()
            last_line_time = 0.0
            for line in resp.iter_lines():
                if not line:
                    continue
                now = time.time()
                # throttle noisy output
                if now - last_line_time < 0.2:
                    continue
                last_line_time = now
                print(line)


def main() -> None:
    tags_url = f"{BASE_URL}/api/tags"
    try:
        r = httpx.get(tags_url, timeout=5.0, verify=False, trust_env=False)
        r.raise_for_status()
    except Exception as e:
        print(f"ERROR: Cannot reach Ollama at {BASE_URL}: {e}")
        sys.exit(1)

    for model in MODELS:
        pull_model(model)

    r = httpx.get(tags_url, timeout=10.0, verify=False, trust_env=False)
    print("\n==> /api/tags:")
    print(r.text)


if __name__ == "__main__":
    main()
