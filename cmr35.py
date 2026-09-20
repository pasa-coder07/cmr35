#!/usr/bin/env python3
import os, sys, shutil, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cmr35_core as core

VIDEO_EXTS = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.3gp', '.ts'}
SEARCH_DIRS = [
    '/sdcard/Download/Convert',
    '/sdcard/Download',
    '/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Video',
    '/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Video/Sent',
    '/sdcard/Movies',
    '/sdcard/DCIM/Camera',
    '/sdcard/DCIM',
]

def scan():
    found = []
    for d in SEARCH_DIRS:
        p = Path(d)
        if not p.is_dir():
            continue
        try:
            for f in sorted(p.iterdir(), key=lambda x: -x.stat().st_mtime):
                if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
                    found.append(f)
        except (PermissionError, OSError):
            continue
        if len(found) >= 30:
            break
    return found

def human_size(n):
    for u in ['B','KB','MB','GB']:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def main():
    ff = shutil.which('ffmpeg'); fp = shutil.which('ffprobe')
    if not ff or not fp:
        sys.exit("ffmpeg yok. Kur: pkg install ffmpeg")

    print("\n" + "="*60)
    print("  CMR35 DONUSTURUCU")
    print("="*60)
    print("\nVideolar taranıyor...\n")

    files = scan()
    if not files:
        print("Video bulunamadi.")
        print("Videoyu /sdcard/Download/Convert klasorune koy.")
        sys.exit(1)

    for i, f in enumerate(files, 1):
        try:
            sz = human_size(f.stat().st_size)
        except OSError:
            sz = "?"
        name = f.name if len(f.name) <= 45 else f.name[:42] + "..."
        print(f"  [{i:2d}] {name:48s} {sz}")

    print()
    while True:
        s = input("Numara (q = cikis): ").strip()
        if s.lower() in ('q','quit','exit'):
            return
        if s.isdigit() and 1 <= int(s) <= len(files):
            src = files[int(s)-1]
            break
        print("Gecersiz.")

    out = src.with_name(f"{src.stem}_CMR35.AVI")
    template = Path(__file__).parent / 'assets' / 'MOV00028.AVI'
    if not template.is_file():
        sys.exit(f"Sablon yok: {template}")

    dur = core.probe_duration(fp, str(src))
    print(f"\n  Kaynak : {src.name}")
    print(f"  Cikti  : {out.name}")
    print(f"  Sure   : {int(dur//60)}dk {int(dur%60)}sn\n")

    tmp = Path(tempfile.mkdtemp(prefix='cmr35_'))
    try:
        norm = tmp / 'norm.avi'
        print("[1/2] Normalize ediliyor...")
        def prog(sec, total):
            if total > 0:
                pct = int(sec / total * 100)
                sys.stdout.write(f"\r  {pct:3d}%  ({int(sec)}/{int(total)}s)")
                sys.stdout.flush()
        core.normalize_input(ff, fp, str(src), str(norm), dur, on_progress=prog)
        print("\n[2/2] CMR35 AVI yapiliyor...")
        size = core.build_output(str(template), str(norm), str(out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    mb = size / (1024*1024)
    print(f"\n  ✓ BITTI!  {mb:.1f} MB  ->  {out}")
    print(f"  Konum: {out.parent}\n")

if __name__ == '__main__':
    main()
