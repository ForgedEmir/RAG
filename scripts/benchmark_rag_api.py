import json
import os
import statistics
import time
import uuid
from typing import Any, Dict, List

import requests

BASE_URL = os.getenv("BENCH_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TARGET_MS = int(os.getenv("BENCH_TARGET_MS", "10000"))
REQUEST_TIMEOUT = int(os.getenv("BENCH_TIMEOUT", "120"))
GUEST_ID = os.getenv("BENCH_GUEST_ID", "guest_benchmark")
BEARER_TOKEN = (os.getenv("BENCH_BEARER_TOKEN", "") or "").strip()
DELAY_SECONDS = float(os.getenv("BENCH_DELAY_SECONDS", "5.2"))
MAX_RETRIES_429 = int(os.getenv("BENCH_MAX_RETRIES_429", "3"))

QUESTIONS = [
    "Qui est Lucas le Tranchant ?",
    "Ou se trouve la Forteresse de l Ombre ?",
    "Que sait-on de l Epee de Vorpal ?",
    "Qui est le roi Alaric ?",
    "Quelles factions existent dans Aethelgard ?",
    "Pourquoi la magie devient instable dans le jeu ?",
]


def _score_quality(answer: str, sources: List[str], confidence: int, model: str) -> float:
    score = 0.0

    if sources or model == "cache":
        score += 30.0

    answer_len = len(answer.strip())
    score += min(30.0, (answer_len / 180.0) * 30.0)

    conf = max(0, min(100, int(confidence or 0)))
    if model == "cache" and conf == 0:
        conf = 85
    score += (conf / 100.0) * 40.0

    return round(min(100.0, score), 1)


def _ask(question: str) -> Dict[str, Any]:
    payload = {
        "question": question,
        "session_id": str(uuid.uuid4()),
    }
    headers = {
        "Content-Type": "application/json",
    }
    if BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
    else:
        headers["x-local-guest-id"] = GUEST_ID

    started = time.perf_counter()
    ttfb_ms = None
    confidence = 0
    sources: List[str] = []
    chunks: List[str] = []
    model = ""

    attempt = 0
    while True:
        attempt += 1
        response = requests.post(
            f"{BASE_URL}/api/ask",
            json=payload,
            headers=headers,
            stream=True,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 429:
            break
        response.close()
        if attempt > MAX_RETRIES_429:
            response.raise_for_status()
        time.sleep(max(DELAY_SECONDS, 5.2))

    with response:
        response.raise_for_status()

        for raw in response.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if not raw.startswith("data: "):
                continue

            if ttfb_ms is None:
                ttfb_ms = int((time.perf_counter() - started) * 1000)

            try:
                event = json.loads(raw[6:])
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            if event_type == "meta":
                confidence = int(event.get("confidence") or 0)
                src = event.get("sources") or []
                if isinstance(src, list):
                    sources = [str(s) for s in src]
            elif event_type == "text":
                text = event.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            elif event_type == "done":
                model = str(event.get("model") or "")
                break

    total_ms = int((time.perf_counter() - started) * 1000)
    answer = "".join(chunks).strip()
    quality = _score_quality(answer, sources, confidence, model)

    return {
        "question": question,
        "total_ms": total_ms,
        "ttfb_ms": ttfb_ms or total_ms,
        "confidence": confidence,
        "sources_count": len(sources),
        "answer_len": len(answer),
        "quality_score": quality,
        "model": model,
        "within_target": total_ms <= TARGET_MS,
    }


def _wait_health(max_wait_s: int = 90) -> None:
    deadline = time.time() + max_wait_s
    last_error = ""
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            if r.status_code in (200, 207):
                return
            last_error = f"status={r.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Server not ready on {BASE_URL}: {last_error}")


def main() -> int:
    _wait_health()

    results: List[Dict[str, Any]] = []
    print(f"Benchmark base_url={BASE_URL} questions={len(QUESTIONS)} target_ms={TARGET_MS}")

    for idx, q in enumerate(QUESTIONS, start=1):
        try:
            row = _ask(q)
            results.append(row)
            flag = "OK" if row["within_target"] else "SLOW"
            print(
                f"Q{idx:02d} total={row['total_ms']}ms ttfb={row['ttfb_ms']}ms "
                f"conf={row['confidence']} src={row['sources_count']} "
                f"len={row['answer_len']} quality={row['quality_score']} model={row['model']} [{flag}]"
            )
        except Exception as exc:
            print(f"Q{idx:02d} ERROR {exc}")

        if idx < len(QUESTIONS) and DELAY_SECONDS > 0:
            time.sleep(DELAY_SECONDS)

    if not results:
        print("No successful requests.")
        return 2

    totals = [r["total_ms"] for r in results]
    ttfb = [r["ttfb_ms"] for r in results]
    quality = [r["quality_score"] for r in results]
    within = [r for r in results if r["within_target"]]

    p50_total = int(statistics.median(totals))
    p95_total = int(sorted(totals)[max(0, int(len(totals) * 0.95) - 1)])
    p50_ttfb = int(statistics.median(ttfb))

    print("---")
    print(f"Summary requests={len(results)}")
    print(f"Total p50={p50_total}ms p95={p95_total}ms max={max(totals)}ms")
    print(f"TTFB  p50={p50_ttfb}ms")
    print(f"Quality avg={round(sum(quality)/len(quality),1)} min={min(quality)} max={max(quality)}")
    print(f"Within target ({TARGET_MS}ms): {len(within)}/{len(results)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
