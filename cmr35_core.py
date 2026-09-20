# -*- coding: utf-8 -*-
import os, struct, subprocess
from pathlib import Path

VIDEO_ID = b'00dc'
AUDIO_ID = b'01wb'
AUDIO_CHUNK_SIZE = 8184
VIDEO_SEGMENT_FRAMES = 60
ALIGN = 512
TARGET_W = 1280
TARGET_H = 720
TARGET_FPS = 30
AUDIO_RATE = 16000

def u32(d,p): return struct.unpack_from('<I', d, p)[0]
def p32(v):   return struct.pack('<I', v)

def _native_dir():
    try:
        from jnius import autoclass
        act = autoclass('org.kivy.android.PythonActivity').mActivity
        return act.getApplicationInfo().nativeLibraryDir
    except Exception:
        return None

def find_ffmpeg():
    # 1) APK içine gömülmüş static ffmpeg (uygulama özel klasöründe)
    try:
        from jnius import autoclass
        act = autoclass('org.kivy.android.PythonActivity').mActivity
        bindir = os.path.join(act.getFilesDir().getAbsolutePath(), 'bin')
        ff = os.path.join(bindir, 'ffmpeg')
        fp = os.path.join(bindir, 'ffprobe')
        if os.path.exists(ff) and os.path.exists(fp):
            return ff, fp, bindir
    except Exception:
        pass
    # 2) Native library fallback
    nd = _native_dir()
    if nd and os.path.isdir(nd):
        ff = os.path.join(nd, 'libffmpeg.so')
        fp = os.path.join(nd, 'libffprobe.so')
        if os.path.exists(ff) and os.path.exists(fp):
            return ff, fp, nd
    # 3) Sistem
    import shutil
    return shutil.which('ffmpeg'), shutil.which('ffprobe'), None
def _env_with_libs(libdir):
    if not libdir:
        return None
    env = os.environ.copy()
    prev = env.get('LD_LIBRARY_PATH', '')
    env['LD_LIBRARY_PATH'] = libdir + (':' + prev if prev else '')
    return env

def probe_duration(ffprobe, src, env=None):
    try:
        o = subprocess.check_output(
            [ffprobe, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=nw=1:nk=1', str(src)], text=True, env=env).strip()
        return float(o)
    except Exception:
        return 0.0

def probe_streams(ffprobe, src, env=None):
    v = subprocess.check_output(
        [ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=codec_name,width,height,r_frame_rate,pix_fmt',
         '-of', 'csv=p=0', str(src)], text=True, env=env).strip().split(',')
    if len(v) < 5:
        raise RuntimeError('Video bilgisi okunamadi')
    a = subprocess.run(
        [ffprobe, '-v', 'error', '-select_streams', 'a:0', '-show_entries',
         'stream=codec_name,sample_rate,channels', '-of', 'csv=p=0', str(src)],
        text=True, capture_output=True, env=env)
    return v, (a.returncode == 0 and a.stdout.strip() != '')

def run_ffmpeg(ffmpeg, args, total_sec, env=None, on_progress=None):
    cmd = [ffmpeg, '-y', '-hide_banner', '-nostats', '-progress', 'pipe:1'] + args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, bufsize=1, env=env)
    errbuf = []
    for raw in proc.stdout:
        line = raw.strip()
        if line.startswith('out_time_ms=') or line.startswith('out_time_us='):
            try:
                us = int(line.split('=', 1)[1])
            except ValueError:
                continue
            sec = us / 1000000.0
            if on_progress:
                on_progress(sec, total_sec)
        else:
            errbuf.append(line)
    proc.wait()
    if proc.returncode != 0:
        tail = '\n'.join(errbuf[-25:])
        raise RuntimeError('ffmpeg hata %d:\n%s' % (proc.returncode, tail))

def normalize_input(ffmpeg, ffprobe, src, out, total_sec, env=None, on_progress=None):
    _, has_audio = probe_streams(ffprobe, src, env)
    vol = os.environ.get('CMR35_VOL', '3.0')
    q = os.environ.get('CMR35_Q', '23')
    dsp = 'highpass=f=120,lowpass=f=7500,volume=%s,alimiter=limit=0.95' % vol
    vf = ('scale=%d:%d:force_original_aspect_ratio=decrease,'
          'pad=%d:%d:(ow-iw)/2:(oh-ih)/2' % (TARGET_W, TARGET_H, TARGET_W, TARGET_H))
    vargs = ['-vf', vf, '-r', str(TARGET_FPS), '-c:v', 'mjpeg', '-q:v', q,
             '-pix_fmt', 'yuvj420p', '-huffman', 'default', '-threads', '0']
    aargs = ['-c:a', 'pcm_s16le', '-ar', str(AUDIO_RATE), '-ac', '1']
    if not has_audio:
        args = ['-i', str(src), '-f', 'lavfi', '-i',
                'anullsrc=r=%d:cl=mono' % AUDIO_RATE,
                '-map', '0:v:0', '-map', '1:a:0']
        args += vargs + aargs + ['-shortest', '-f', 'avi', str(out)]
    else:
        args = ['-i', str(src), '-map', '0:v:0', '-map', '0:a:0']
        args += vargs + ['-af', dsp] + aargs + ['-f', 'avi', str(out)]
    run_ffmpeg(ffmpeg, args, total_sec, env=env, on_progress=on_progress)

def find_movi(d):
    p = d.find(b'LIST')
    while p >= 0 and p + 12 <= len(d):
        if d[p:p+4] == b'LIST' and d[p+8:p+12] == b'movi':
            return p, p+12, p+8+u32(d, p+4)
        p = d.find(b'LIST', p+4)
    raise RuntimeError('movi LIST bulunamadi')

def parse_movi_chunks(d):
    _, start, end = find_movi(d)
    vids, auds = [], []
    p = start
    while p + 8 <= end:
        cid, size = d[p:p+4], u32(d, p+4)
        pe = p + 8 + size
        if pe > end: break
        if cid == VIDEO_ID: vids.append(d[p+8:pe])
        elif cid == AUDIO_ID: auds.append(d[p+8:pe])
        p = pe + (size & 1)
    return vids, auds

def locate_chunks(t):
    out = {k: None for k in ['avih','dmlh','video_strh','audio_strh',
                             'video_strf','audio_strf','indx_video','indx_audio']}
    def walk(s, e):
        q = s
        while q + 8 <= e:
            cid, size = t[q:q+4], u32(t, q+4)
            ce = q + 8 + size
            if ce > e: return
            if cid == b'LIST': walk(q+12, ce)
            else:
                if cid == b'avih': out['avih'] = q
                elif cid == b'dmlh': out['dmlh'] = q
                elif cid == b'strh' and size >= 12:
                    if t[q+8:q+12] == b'vids': out['video_strh'] = q
                    elif t[q+8:q+12] == b'auds': out['audio_strh'] = q
                elif cid == b'strf':
                    out['video_strf' if q < 14848 else 'audio_strf'] = q
                elif cid == b'indx' and size >= 24:
                    cid2 = t[q+16:q+20]
                    if cid2 == b'00dc': out['indx_video'] = q
                    elif cid2 == b'01wb': out['indx_audio'] = q
            q = ce + (size & 1)
    walk(12, len(t))
    return out

def patch_avih(buf, pos, frames):
    b = pos + 8
    buf[b:b+40] = struct.pack('<10I', 33333, 0, 0, 0x30, frames, 0, 2,
                              1048576, TARGET_W, TARGET_H)

def patch_strh(buf, pos, kind, frames, audio_bytes):
    b = pos + 8
    if kind == 'video':
        buf[b:b+48] = struct.pack('<4s4s10I', b'vids', b'MJPG', 0, 0, 0, 1,
                                  TARGET_FPS, 0, frames, 1048576, 0xFFFFFFFF, 0)
    else:
        buf[b:b+48] = struct.pack('<4s4s10I', b'auds', b'\x00\x00\x00\x00',
                                  0, 0, 0, 2, AUDIO_RATE*2, 0,
                                  audio_bytes // 2, 65536, 0xFFFFFFFF, 2)

def patch_strf(buf, pos, kind):
    b = pos + 8
    if kind == 'video':
        buf[b:b+24] = struct.pack('<IIIHH4sI', 40, TARGET_W, TARGET_H, 1, 24, b'MJPG', 0)
    else:
        buf[b:b+16] = struct.pack('<HHIIHH', 1, 1, AUDIO_RATE, AUDIO_RATE*2, 2, 16)

def patch_dmlh(buf, pos, frames):
    buf[pos+8:pos+12] = p32(frames)

def make_ix(cid, base_offset, entries):
    ixid = b'ix00' if cid == VIDEO_ID else b'ix01'
    payload = struct.pack('<HBBI4sQI', 2, 0, 1, len(entries), cid, base_offset, 0)
    for off, size in entries:
        payload += struct.pack('<II', off, size)
    return ixid + p32(len(payload)) + payload + (b'\x00' if len(payload) & 1 else b'')

def patch_superindex(buf, pos, cid, blocks):
    size, ps = u32(buf, pos+4), pos + 8
    buf[ps:ps+size] = b'\x00' * size
    buf[ps:ps+24] = struct.pack('<HBBI4sQI', 4, 0, 0, len(blocks), cid, 0, 0)
    ep = ps + 24
    for off, total, dur in blocks:
        buf[ep:ep+16] = struct.pack('<QII', off, total, dur)
        ep += 16

def pad_video_payload(j):
    rem = (len(j) + 8) % ALIGN
    return j if rem == 0 else j + b'\x00' * (ALIGN - rem)

def schedule_audio_thresholds(vcount, acount):
    known = [4,14,21,29,38,44,53,60,68,76,83,92,99,106,115]
    if acount <= len(known):
        return known[:acount]
    out = known[:]
    last, acc = out[-1], 0.0
    for i in range(len(out), acount):
        acc += 8184 * TARGET_FPS / (AUDIO_RATE * 2)
        d = max(7, min(8, int(acc)))
        acc -= int(acc)
        last += d
        out.append(min(vcount, last))
    for i in range(1, len(out)):
        if out[i] <= out[i-1]:
            out[i] = min(vcount, out[i-1] + 1)
    return out

def build_output(template_path, normalized_path, output_path):
    template = Path(template_path).read_bytes()
    norm = Path(normalized_path).read_bytes()
    t_movi, t_movi_data, _ = find_movi(template)
    videos, src_audios = parse_movi_chunks(norm)
    pcm = b''.join(src_audios)
    audio_chunks = [pcm[i:i+AUDIO_CHUNK_SIZE]
                    for i in range(0, len(pcm), AUDIO_CHUNK_SIZE)
                    if pcm[i:i+AUDIO_CHUNK_SIZE]]
    frame_count, audio_bytes = len(videos), len(pcm)
    header = bytearray(template[:t_movi_data])
    cam_prefix = template[t_movi_data:]
    hm_prefix = b''
    if cam_prefix[:4] == b'JUNK' and u32(cam_prefix, 4) == 3064:
        hm_prefix = cam_prefix[:3072]
    loc = locate_chunks(header)
    patch_avih(header, loc['avih'], frame_count)
    patch_strh(header, loc['video_strh'], 'video', frame_count, audio_bytes)
    patch_strh(header, loc['audio_strh'], 'audio', frame_count, audio_bytes)
    patch_strf(header, loc['video_strf'], 'video')
    patch_strf(header, loc['audio_strf'], 'audio')
    patch_dmlh(header, loc['dmlh'], frame_count)
    final = bytearray(hm_prefix)
    recs = []
    base_off = t_movi + 8
    movi_abs = t_movi + 12
    def junk512(buf):
        rem = (movi_abs + len(buf)) % ALIGN
        if rem == 0: return
        total = ALIGN - rem
        if total < 8: total += ALIGN
        js = total - 8
        if js & 1: js += 1
        buf.extend(b'JUNK' + p32(js) + b'\x00' * js)
    segs, cur, ai = [], [], 0
    thr = schedule_audio_thresholds(frame_count, len(audio_chunks))
    for i, raw in enumerate(videos, 1):
        cur.append((VIDEO_ID, pad_video_payload(raw)))
        if i % VIDEO_SEGMENT_FRAMES == 0 and i != frame_count:
            segs.append(cur); cur = []
            while ai < len(audio_chunks) and thr[ai] == i:
                cur.append((AUDIO_ID, audio_chunks[ai])); ai += 1
            continue
        while ai < len(audio_chunks) and thr[ai] == i:
            cur.append((AUDIO_ID, audio_chunks[ai])); ai += 1
    if cur: segs.append(cur)
    while ai < len(audio_chunks):
        if not segs: segs.append([])
        segs[-1].append((AUDIO_ID, audio_chunks[ai])); ai += 1
    for si, seg in enumerate(segs):
        ve, ae = [], []
        for cid, pl in seg:
            rel = len(final)
            final.extend(cid + p32(len(pl)) + pl + (b'\x00' if len(pl) & 1 else b''))
            ap = movi_abs + rel + 8
            (ve if cid == VIDEO_ID else ae).append((ap, len(pl)))
        if ve:
            pos = movi_abs + len(final)
            ix = make_ix(VIDEO_ID, base_off, [(p-base_off, s) for p, s in ve])
            recs.append(('v', pos, len(ix), len(ve))); final.extend(ix)
        if ae:
            pos = movi_abs + len(final)
            ix = make_ix(AUDIO_ID, base_off, [(p-base_off, s) for p, s in ae])
            recs.append(('a', pos, len(ix), len(ae))); final.extend(ix)
        if si != len(segs) - 1: junk512(final)
    junk512(final)
    vs, as_ = [], []
    for typ, p, sz, cnt in recs:
        if typ == 'v':
            vs.append((p, sz, cnt))
        else:
            ps = p - movi_abs + 8
            n = u32(final, ps + 4)
            tot = 0; ep = ps + 24
            for _ in range(n):
                tot += u32(final, ep + 8); ep += 8
            as_.append((p, sz, tot // 2))
    patch_superindex(header, loc['indx_video'], VIDEO_ID, vs)
    patch_superindex(header, loc['indx_audio'], AUDIO_ID, as_)
    header[t_movi+4:t_movi+8] = p32(4 + len(final))
    output = bytearray(header) + final
    output[4:8] = p32(len(output) - 8)
    Path(output_path).write_bytes(output)
    return len(output)
