#!/usr/bin/env python3
import os, sys, shutil, tempfile, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cmr35_core as core


def find_ffmpeg():
    ff = shutil.which('ffmpeg')
    fp = shutil.which('ffprobe')
    if not ff or not fp:
        sys.exit("ffmpeg bulunamadi. Kur: pkg install ffmpeg")
    return ff, fp, None


def main():
    if len(sys.argv) < 2:
        print("Kullanim: python cmr35_cli.py video.mp4 [cikti.avi]")
        print("Ornek  : python cmr35_cli.py /sdcard/Download/Convert/klip.mp4")
        sys.exit(1)

    src = Path(sys.argv[1]).resolve()
    if not src.is_file():
        sys.exit(f"Kaynak yok: {src}")

    out = Path(sys.argv[2]).resolve() if len(sys.argv) >= 3 \
          else src.with_name(f"{src.stem}_CMR35.AVI")

    template = Path(__file__).parent / 'assets' / 'MOV00028.AVI'
    if not template.is_file():
        sys.exit(f"Sablon yok: {template}")

    ff, fp, _ = find_ffmpeg()
    dur = core.probe_duration(fp, src)

    print(f"Kaynak : {src}")
    print(f"Cikti  : {out}")
    print(f"Sablon : {template}")
    print(f"Sure   : {int(dur//60)}dk {int(dur%60)}sn\n")

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
        print()

        print("[2/2] CMR35 AVI olusturuluyor...")
        size = core.build_output(str(template), str(norm), str(out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    mb = size / (1024*1024)
    print(f"\nBITTI!  {mb:.1f} MB  ->  {out}")


if __name__ == '__main__':
    main()
