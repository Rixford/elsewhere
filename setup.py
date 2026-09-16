"""Explicit, one-time online setup. The application never calls this script."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ['LOCALAPPDATA']) / 'Elsewhere'
FILES = [
    ('llama-b11007.zip', 'https://github.com/ggml-org/llama.cpp/releases/download/b11007/llama-b11007-bin-win-vulkan-x64.zip', 'da306942a67f5806f3715f5f82978158775b71d66c8560f64a91a549b6b6d34d'),
    ('models/Qwen3.5-4B-Q4_K_M.gguf', 'https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf', '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'),
    ('models/mmproj-F16.gguf', 'https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/mmproj-F16.gguf', 'cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864'),
]

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def download(item):
    name, url, digest = item
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and sha(path) == digest:
        print(f'Verified: {name}', flush=True)
        return
    partial = path.with_suffix(path.suffix + '.part')
    for attempt in range(3):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            req = urllib.request.Request(url, headers={'User-Agent': 'Elsewhere-Setup/1.0', 'Range': f'bytes={offset}-'})
            with urllib.request.urlopen(req, timeout=90) as source:
                resume = source.status == 206 and offset > 0
                total = int(source.headers.get('Content-Length', 0)) + (offset if resume else 0)
                done = offset if resume else 0
                stamp = 0
                with partial.open('ab' if resume else 'wb') as out:
                    while chunk := source.read(4 * 1024 * 1024):
                        out.write(chunk)
                        done += len(chunk)
                        if time.monotonic() - stamp > 10:
                            print(f'{name}: {done / 1e6:.0f} / {total / 1e6:.0f} MB', flush=True)
                            stamp = time.monotonic()
            if sha(partial) != digest:
                partial.unlink()
                raise ValueError(f'SHA256 mismatch: {name}')
            partial.replace(path)
            print(f'Verified download: {name}', flush=True)
            return
        except Exception as exc:
            print(f'{name}: attempt {attempt + 1}: {exc}', flush=True)
            if attempt == 2:
                raise
            time.sleep(2)

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, FILES))
    runtime = DATA / 'runtime'
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(DATA / FILES[0][0]) as bundle:
        for member in bundle.infolist():
            if not (runtime / member.filename).resolve().is_relative_to(runtime.resolve()):
                raise ValueError('Unsafe archive path')
        bundle.extractall(runtime)
    python = DATA / 'python' / 'Scripts' / 'python.exe'
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(DATA / 'python')], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
    physical_data = subprocess.check_output([str(python), '-c', 'from pathlib import Path; import sys; print(Path(sys.executable).resolve().parents[2])'], text=True).strip()
    (ROOT / 'runtime-path.txt').write_text(physical_data, encoding='utf-8')
    (DATA / 'installation.json').write_text(json.dumps({'downloads': FILES, 'model': 'Qwen3.5-4B Q4_K_M', 'llama': 'b11007'}, indent=2))
    print('Setup complete. Open Start Elsewhere.vbs. Normal use is offline.', flush=True)

if __name__ == '__main__':
    main()
