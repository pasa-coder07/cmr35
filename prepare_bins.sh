#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p libs/arm64-v8a

cp "$PREFIX/bin/ffmpeg"  libs/arm64-v8a/libffmpeg.so
cp "$PREFIX/bin/ffprobe" libs/arm64-v8a/libffprobe.so
chmod +x libs/arm64-v8a/*.so

for bin in ffmpeg ffprobe; do
  ldd "$PREFIX/bin/$bin" | grep "$PREFIX" | awk '{print $3}' | while read so; do
    [ -f "$so" ] && cp -n "$so" libs/arm64-v8a/ 2>/dev/null || true
  done
done

echo "=== libs/arm64-v8a ==="
ls -lh libs/arm64-v8a/
