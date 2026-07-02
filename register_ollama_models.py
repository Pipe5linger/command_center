"""
Register all 13 Ollama Modelfiles into the running Ollama server.
Mirrors setup_ollama.bat but uses subprocess with proper timeout/streaming,
avoids the trailing `pause`, and writes a structured log.
"""
import subprocess
import sys
import time
from pathlib import Path

MODELDIR = Path(r"D:\AI\Models\LLM\Ollama_Modelfiles")
LOG_PATH = MODELDIR / "register_ollama_models.log"

# (ollama_model_name, modelfile_basename)
MODELS = [
    ("qwen2.5-coder-vespera:latest",   "qwen2.5-coder-vespera.Modelfile"),
    ("vespera-original:latest",         "vespera-original.Modelfile"),
    ("deepseek-r1-vespera:latest",     "deepseek-r1-vespera.Modelfile"),
    ("qwen-coder-14b:latest",          "qwen-coder-14b.Modelfile"),
    ("mistral-nemo:latest",            "mistral-nemo.Modelfile"),
    ("gemma4-uncensored:latest",       "gemma4-12b-uncensored.Modelfile"),
    ("llama3.1-lexi:latest",           "llama3.1-lexi-uncensored.Modelfile"),
    ("qwythos-9b:latest",              "qwythos-9b.Modelfile"),
    ("ornith-9b:latest",               "ornith-9b.Modelfile"),
    ("llama3:latest",                  "llama3-base.Modelfile"),
    ("llava:latest",                   "llava-vision.Modelfile"),
    ("nsfw-prompt-gen:latest",         "nsfw-prompt-generator.Modelfile"),
    ("nomic-embed-text:latest",        "nomic-embed-text.Modelfile"),
]


def run_ollama_create(name: str, modelfile: Path) -> tuple[bool, str, float]:
    """Run `ollama create <name> -f <modelfile>`. Returns (ok, output, elapsed_sec)."""
    cmd = ["ollama", "create", name, "-f", str(modelfile)]
    print(f"\n[CREATE] {name}")
    print(f"  CMD: {' '.join(cmd)}")
    t0 = time.time()
    try:
        # Modelfile parsing is quick; create is a metadata op. 2 min cap.
        result = subprocess.run(
            cmd,
            cwd=str(MODELDIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.time() - t0
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0:
            print(f"  OK   ({elapsed:.1f}s) :: {output.strip()[:200]}")
            return True, output, elapsed
        print(f"  FAIL ({elapsed:.1f}s, rc={result.returncode}) :: {output.strip()[:400]}")
        return False, output, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        msg = f"TIMEOUT after {elapsed:.0f}s"
        print(f"  {msg}")
        return False, msg, elapsed
    except FileNotFoundError as e:
        msg = f"ollama executable not found: {e}"
        print(f"  FAIL :: {msg}")
        return False, msg, 0.0


def main() -> int:
    log_lines = []
    successes = []
    failures = []

    print(f"Ollama Modelfile Registration")
    print(f"Model dir: {MODELDIR}")
    print(f"Total models to register: {len(MODELS)}")
    print("=" * 60)

    for name, mf in MODELS:
        mf_path = MODELDIR / mf
        if not mf_path.exists():
            msg = f"Modelfile missing: {mf_path}"
            print(f"  SKIP :: {msg}")
            failures.append((name, msg))
            log_lines.append(f"[SKIP] {name} :: {msg}")
            continue

        ok, output, elapsed = run_ollama_create(name, mf_path)
        status = "OK" if ok else "FAIL"
        log_lines.append(f"[{status}] {name} :: {elapsed:.1f}s :: {output.strip()[:200]}")
        (successes if ok else failures).append((name, output.strip()[:200]))

    print("\n" + "=" * 60)
    print(f"Done. Success: {len(successes)}/{len(MODELS)}  Failures: {len(failures)}")
    for n, o in failures:
        print(f"  [FAIL] {n}")
        print(f"         {o}")
    print("=" * 60)

    log_lines.append("")
    log_lines.append(f"Summary: {len(successes)} ok, {len(failures)} failed, {len(MODELS)} total")
    LOG_PATH.write_text("\n".join(log_lines), encoding="utf-8")
    print(f"\nLog: {LOG_PATH}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
