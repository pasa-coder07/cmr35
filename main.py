# -*- coding: utf-8 -*-
import os, threading, shutil, time
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (StringProperty, NumericProperty,
                             BooleanProperty, ListProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.utils import platform

import cmr35_core as core


VOLUME_STEPS = [50, 75, 100, 125, 150, 200, 250, 300,
                400, 500, 700, 1000]
DEFAULT_VOL_IDX = 7
SEGMENT_SEC = 180  # 3 dakika parca boyu

VIDEO_FILTERS = ['*.mp4', '*.mkv', '*.mov', '*.avi', '*.webm',
                 '*.m4v', '*.3gp', '*.ts']


def human_size(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return '%.1f %s' % (n, u)
        n /= 1024
    return '%.1f TB' % n


def request_permissions():
    if platform != 'android':
        return
    try:
        from android.permissions import request_permissions as rp, Permission
        from jnius import autoclass
        Build = autoclass('android.os.Build$VERSION')
        sdk = Build.SDK_INT
        perms = []
        if sdk >= 33:
            perms = [Permission.READ_MEDIA_VIDEO,
                     'android.permission.POST_NOTIFICATIONS']
        elif sdk >= 23:
            perms = [Permission.READ_EXTERNAL_STORAGE]
            if sdk < 30:
                perms.append(Permission.WRITE_EXTERNAL_STORAGE)
        if perms:
            rp(perms)
        if sdk >= 30:
            Clock.schedule_once(lambda dt: _open_all_files_settings(), 1.5)
    except Exception as e:
        print('izin hata:', e)


def _open_all_files_settings():
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Settings = autoclass('android.provider.Settings')
        Uri = autoclass('android.net.Uri')
        Build = autoclass('android.os.Build$VERSION')
        act = PythonActivity.mActivity
        if Build.SDK_INT < 30:
            return
        Environment = autoclass('android.os.Environment')
        if Environment.isExternalStorageManager():
            return
        pkg = act.getPackageName()
        intent = Intent(
            Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        intent.setData(Uri.parse('package:' + pkg))
        act.startActivity(intent)
    except Exception as e:
        print('settings hata:', e)


def keep_screen_on():
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
        act = PythonActivity.mActivity
        act.getWindow().addFlags(LayoutParams.FLAG_KEEP_SCREEN_ON)
    except Exception as e:
        print('keep_screen hata:', e)


def send_notification(title, message):
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        Intent = autoclass('android.content.Intent')
        PendingIntent = autoclass('android.app.PendingIntent')
        Notification = autoclass('android.app.Notification')
        NotificationManager = autoclass('android.app.NotificationManager')
        Build = autoclass('android.os.Build$VERSION')
        act = PythonActivity.mActivity
        ctx = act.getApplicationContext()
        ns = ctx.getSystemService(Context.NOTIFICATION_SERVICE)
        ch_id = 'cmr35'
        if Build.SDK_INT >= 26:
            NotificationChannel = autoclass(
                'android.app.NotificationChannel')
            ch = NotificationChannel(ch_id, 'CMR35',
                                     NotificationManager.IMPORTANCE_HIGH)
            ns.createNotificationChannel(ch)
        intent = Intent(ctx, PythonActivity)
        flags = 0x04000000
        if Build.SDK_INT < 23:
            flags = 0
        pi = PendingIntent.getActivity(ctx, 0, intent, flags)
        if Build.SDK_INT >= 26:
            b = Notification.Builder(ctx, ch_id)
        else:
            b = Notification.Builder(ctx)
        b.setContentTitle(title)
        b.setContentText(message)
        b.setSmallIcon(17301633)
        b.setContentIntent(pi)
        b.setAutoCancel(True)
        ns.notify(1, b.build())
    except Exception as e:
        print('notif hata:', e)


def extract_ffmpeg():
    if platform != 'android':
        return
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        act = PythonActivity.mActivity
        bindir = os.path.join(act.getFilesDir().getAbsolutePath(), 'bin')
        os.makedirs(bindir, exist_ok=True)
        assets = act.getAssets()
        for name in ('ffmpeg', 'ffprobe', 'MOV00028.AVI'):
            target = os.path.join(bindir, name)
            if os.path.exists(target) and os.path.getsize(target) > 1000:
                continue
            try:
                istream = assets.open('bin/' + name)
            except Exception:
                continue
            with open(target, 'wb') as out:
                buf = bytearray(65536)
                while True:
                    n = istream.read(buf)
                    if n <= 0:
                        break
                    out.write(bytes(buf[:n]))
            istream.close()
            if name in ('ffmpeg', 'ffprobe'):
                os.chmod(target, 0o755)
    except Exception as e:
        print('extract hata:', e)


def import_shared_video():
    if platform != 'android':
        return None
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        act = PythonActivity.mActivity
        intent = act.getIntent()
        if intent is None or intent.getAction() != Intent.ACTION_SEND:
            return None
        uri = None
        try:
            Parcelable = autoclass('android.os.Parcelable')
            uri = intent.getParcelableExtra(Intent.EXTRA_STREAM, Parcelable)
        except Exception:
            pass
        if uri is None:
            try:
                uri = intent.getParcelableExtra(Intent.EXTRA_STREAM)
            except Exception:
                pass
        if uri is None:
            return None
        bindir = os.path.join(
            act.getFilesDir().getAbsolutePath(), 'shared')
        os.makedirs(bindir, exist_ok=True)
        dst = os.path.join(bindir, 'shared_%d.mp4' % int(time.time()))
        stream = act.getContentResolver().openInputStream(uri)
        if stream is None:
            return None
        buf = bytearray(65536)
        with open(dst, 'wb') as out:
            while True:
                n = stream.read(buf)
                if n <= 0:
                    break
                out.write(bytes(buf[:n]))
        stream.close()
        return dst
    except Exception as e:
        print('shared hata:', e)
        return None


KV = '''
<Root>:
    orientation: 'vertical'
    padding: dp(14)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: 0.07, 0.07, 0.09, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: 'CMR35'
        font_size: '28sp'
        bold: True
        color: 0.16, 0.82, 0.44, 1
        size_hint_y: None
        height: dp(32)
    Label:
        text: 'Video  ->  Kamera AVI'
        font_size: '11sp'
        color: 0.55, 0.55, 0.62, 1
        size_hint_y: None
        height: dp(16)

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(100)
        padding: dp(14), dp(10)
        spacing: dp(4)
        canvas.before:
            Color:
                rgba: 0.13, 0.13, 0.16, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(14)]
        Label:
            text: root.status
            font_size: '15sp'
            bold: True
            color: 1, 1, 1, 1
            size_hint_y: None
            height: dp(24)
            text_size: self.width, None
            halign: 'center'
        Label:
            text: root.info
            font_size: '10sp'
            color: 0.62, 0.62, 0.68, 1
            text_size: self.width, None
            halign: 'center'
            valign: 'top'

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(85)
        spacing: dp(3)
        Label:
            text: 'Ses: ' + root.volume_label
            font_size: '13sp'
            bold: True
            color: 0.9, 0.9, 0.95, 1
            size_hint_y: None
            height: dp(22)
            text_size: self.width, None
            halign: 'center'
        Slider:
            min: 0
            max: 11
            step: 1
            value: root.vol_index
            size_hint_y: None
            height: dp(30)
            on_value: root._on_slider(self.value)
        BoxLayout:
            size_hint_y: None
            height: dp(30)
            spacing: dp(6)
            Button:
                text: '-'
                size_hint_x: None
                width: dp(50)
                font_size: '20sp'
                bold: True
                on_release: root.vol_step(-1)
            TextInput:
                text: root.volume_percent_str
                input_filter: 'int'
                input_type: 'number'
                multiline: False
                font_size: '14sp'
                halign: 'center'
                on_text_validate: root.set_from_text(self.text)
            Label:
                text: '%'
                size_hint_x: None
                width: dp(22)
                color: 0.75, 0.75, 0.80, 1
            Button:
                text: '+'
                size_hint_x: None
                width: dp(50)
                font_size: '20sp'
                bold: True
                on_release: root.vol_step(1)

    ProgressBar:
        max: 1.0
        value: root.progress
        size_hint_y: None
        height: dp(8)

    ScrollView:
        size_hint_y: None
        height: dp(90) if len(root.queue) > 0 else 0
        opacity: 1 if len(root.queue) > 0 else 0
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(6)
            canvas.before:
                Color:
                    rgba: 0.10, 0.10, 0.12, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(10)]
            Label:
                text: root.queue_label
                font_size: '10sp'
                color: 0.75, 0.75, 0.80, 1
                size_hint_y: None
                height: self.texture_size[1]
                text_size: self.width, None
                halign: 'left'

    Widget:
        size_hint_y: None
        height: dp(2)

    BoxLayout:
        size_hint_y: None
        height: dp(58)
        spacing: dp(8)
        Button:
            text: 'Video Sec'
            font_size: '14sp'
            bold: True
            color: 1, 1, 1, 1
            background_normal: ''
            background_disabled_normal: ''
            background_color: 0, 0, 0, 0
            disabled: root.busy
            canvas.before:
                Color:
                    rgba: (0.16, 0.82, 0.44, 1) if not self.disabled else (0.35, 0.35, 0.38, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12)]
            on_release: root.pick(single=True)
        Button:
            text: 'Toplu Sec'
            font_size: '14sp'
            bold: True
            color: 1, 1, 1, 1
            background_normal: ''
            background_disabled_normal: ''
            background_color: 0, 0, 0, 0
            disabled: root.busy
            canvas.before:
                Color:
                    rgba: (0.20, 0.55, 0.85, 1) if not self.disabled else (0.35, 0.35, 0.38, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12)]
            on_release: root.pick(single=False)

    Button:
        text: ('Donustur' if len(root.queue) <= 1 else 'Kuyrugu Baslat') if not root.busy else ('Iptal' if not root.canceling else 'Iptal ediliyor...')
        font_size: '15sp'
        bold: True
        color: 1, 1, 1, 1
        size_hint_y: None
        height: dp(58)
        background_normal: ''
        background_disabled_normal: ''
        background_color: 0, 0, 0, 0
        disabled: (len(root.queue) == 0 and not root.busy) or root.canceling
        canvas.before:
            Color:
                rgba: (0.85, 0.20, 0.20, 1) if root.busy else ((1, 0.45, 0, 1) if len(root.queue) > 0 else (0.35, 0.35, 0.38, 1))
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(12)]
        on_release: root.cancel() if root.busy else root.start_batch()
'''


class Root(BoxLayout):
    status = StringProperty('Izin kontrol ediliyor...')
    info = StringProperty('Lutfen bekleyin')
    progress = NumericProperty(0.0)
    vol_index = NumericProperty(DEFAULT_VOL_IDX)
    volume_label = StringProperty('300%')
    volume_percent_str = StringProperty('300')
    busy = BooleanProperty(False)
    canceling = BooleanProperty(False)
    queue = ListProperty([])
    queue_label = StringProperty('')
    src = StringProperty('')

    @property
    def volume(self):
        idx = max(0, min(len(VOLUME_STEPS) - 1, int(round(self.vol_index))))
        return VOLUME_STEPS[idx] / 100.0

    def _on_slider(self, value):
        idx = int(round(value))
        if idx != int(round(self.vol_index)):
            self.vol_index = idx

    def on_vol_index(self, *a):
        idx = max(0, min(len(VOLUME_STEPS) - 1, int(round(self.vol_index))))
        pct = VOLUME_STEPS[idx]
        self.volume_label = '%d%%' % pct
        self.volume_percent_str = str(pct)

    def set_vol_index(self, idx):
        if idx < 0:
            idx = 0
        if idx >= len(VOLUME_STEPS):
            idx = len(VOLUME_STEPS) - 1
        self.vol_index = idx

    def vol_step(self, delta):
        self.set_vol_index(int(round(self.vol_index)) + delta)

    def set_from_text(self, text):
        try:
            pct = int(str(text).strip())
        except (ValueError, TypeError):
            return
        pct = max(10, min(2000, pct))
        best, diff = 0, abs(VOLUME_STEPS[0] - pct)
        for i, v in enumerate(VOLUME_STEPS):
            d = abs(v - pct)
            if d < diff:
                diff = d
                best = i
        self.set_vol_index(best)

    def on_queue(self, *a):
        if not self.queue:
            self.queue_label = ''
            return
        lines = []
        for i, p in enumerate(self.queue[:6], 1):
            n = os.path.basename(p)
            if len(n) > 38:
                n = n[:35] + '...'
            lines.append('%d. %s' % (i, n))
        if len(self.queue) > 6:
            lines.append('... +%d daha' % (len(self.queue) - 6))
        self.queue_label = '\n'.join(lines)

    def on_kv_post(self, base_widget):
        self.on_vol_index()
        Clock.schedule_once(lambda dt: self._ask_permissions(), 0.4)

    def _ask_permissions(self):
        try:
            request_permissions()
            Clock.schedule_once(lambda dt: self._after_perms(), 3.0)
        except Exception as e:
            print('perms hata:', e)
            self._after_perms()

    def _after_perms(self):
        self.status = 'Hazir'
        self.info = 'Donusturmek icin video secin'
        try:
            path = import_shared_video()
            if path and os.path.isfile(path):
                self.queue = [path]
                size = human_size(os.path.getsize(path))
                self.status = 'Paylasilan video hazir'
                self.info = '%s  -  %s' % (os.path.basename(path), size)
        except Exception as e:
            print('on_start hata:', e)

    def _best_dir(self):
        for d in ['/sdcard/Download', '/storage/emulated/0/Download',
                  '/sdcard/Movies', '/sdcard/DCIM', '/sdcard']:
            if os.path.isdir(d):
                return d
        return '/sdcard'

    def _app_dir(self):
        try:
            from android.storage import app_storage_path
            return app_storage_path()
        except Exception:
            return os.path.expanduser('~')

    def _set_status(self, msg):
        Clock.schedule_once(lambda *_: setattr(self, 'status', msg))

    def _set_info(self, msg):
        Clock.schedule_once(lambda *_: setattr(self, 'info', msg))

    def _set_busy(self, val):
        Clock.schedule_once(lambda *_: setattr(self, 'busy', val))

    def _set_canceling(self, val):
        Clock.schedule_once(lambda *_: setattr(self, 'canceling', val))

    def _set_progress(self, val):
        Clock.schedule_once(lambda *_: setattr(self, 'progress', val))

    def _template_path(self):
        try:
            from jnius import autoclass
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            bindir = os.path.join(
                act.getFilesDir().getAbsolutePath(), 'bin')
            p = os.path.join(bindir, 'MOV00028.AVI')
            if os.path.isfile(p):
                return p
        except Exception:
            pass
        for d in ['/sdcard/Download', '/sdcard',
                  '/storage/emulated/0/Download']:
            p = os.path.join(d, 'MOV00028.AVI')
            if os.path.isfile(p):
                return p
        return None

    def pick(self, single=True):
        box = BoxLayout(orientation='vertical')
        fc = FileChooserListView(
            path=self._best_dir(),
            filters=VIDEO_FILTERS,
            multiselect=not single)
        box.add_widget(fc)
        title = 'Video Sec' if single else 'Toplu Sec (birden fazla)'
        pop = Popup(title=title, content=box, size_hint=(0.95, 0.95))

        def _go(*a):
            sel = list(fc.selection) if fc.selection else []
            if sel:
                if single:
                    self.queue = [sel[0]]
                    try:
                        size = human_size(os.path.getsize(sel[0]))
                    except OSError:
                        size = '?'
                    self.status = 'Video hazir'
                    self.info = '%s  -  %s' % (
                        os.path.basename(sel[0]), size)
                else:
                    self.queue = sel
                    self.status = 'Kuyruk hazir (%d video)' % len(sel)
                    self.info = 'Kuyrugu Baslat butonuna basin'
            pop.dismiss()

        btn = Button(text='Sec', size_hint_y=None, height='48dp')
        btn.bind(on_release=_go)
        box.add_widget(btn)
        pop.open()

    def cancel(self):
        if not self.busy or self.canceling:
            return
        self.canceling = True
        self.status = 'Iptal ediliyor...'
        core.request_cancel()

    def start_batch(self):
        if not self.queue or self.busy:
            return
        self.busy = True
        self.status = 'Basliyor...'
        self.progress = 0.0
        threading.Thread(target=self._batch_worker, daemon=True).start()

    def _share(self, path):
        if platform != 'android':
            return
        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            File = autoclass('java.io.File')
            i = Intent(Intent.ACTION_SEND)
            i.setType('video/avi')
            u = Uri.fromFile(File(path))
            i.putExtra(Intent.EXTRA_STREAM,
                       cast('android.os.Parcelable', u))
            PythonActivity.mActivity.startActivity(
                Intent.createChooser(i, 'Paylas'))
        except Exception:
            pass

    def _cut_segment(self, ff, src, start, dur, out, env):
        args = ['-ss', str(start), '-i', str(src), '-t', str(dur),
                '-c', 'copy', '-avoid_negative_ts', 'make_zero',
                '-y', str(out)]
        core.run_ffmpeg(ff, args, 0, env=env)

    def _encode_segment(self, src, tmpl, ff, fp, env, appdir,
                        dur, prefix, part_i, part_n, base_name):
        norm = os.path.join(appdir, 'norm_%d.avi' % part_i)
        outtmp = os.path.join(appdir, 'out_%d.avi' % part_i)

        self._set_status('%sEncode: %ddk %dsn' % (
            prefix, int(dur // 60), int(dur % 60)))
        self._set_info(os.path.basename(base_name))

        def prog(sec, total_sec):
            if total_sec > 0:
                frac = min(0.98, sec / total_sec)
                if part_n > 1:
                    self._set_progress(((part_i - 1) + frac) / part_n)
                else:
                    self._set_progress(frac)

        core.normalize_input(ff, fp, src, norm, dur,
                             volume=self.volume, env=env,
                             on_progress=prog)
        self._set_status('%sAVI insa ediliyor...' % prefix)
        core.build_output(tmpl, norm, outtmp)

        if part_n > 1:
            base = base_name.rsplit('.', 1)[0]
            out = '%s_part%d_CMR35.AVI' % (base, part_i)
        else:
            out = base_name.rsplit('.', 1)[0] + '_CMR35.AVI'

        try:
            shutil.move(outtmp, out)
        except Exception:
            out = outtmp
        try:
            os.remove(norm)
        except OSError:
            pass
        return out

    def _process_one(self, src, idx, total):
        extract_ffmpeg()
        ff, fp, libdir = core.find_ffmpeg()
        if not ff or not fp:
            raise RuntimeError('ffmpeg bulunamadi')
        env = core._env_with_libs(libdir)
        tmpl = self._template_path()
        if not tmpl:
            raise RuntimeError('Sablon MOV00028.AVI yok')

        appdir = self._app_dir()
        dur = core.probe_duration(fp, src, env)
        prefix = '[%d/%d] ' % (idx, total) if total > 1 else ''

        if dur <= SEGMENT_SEC + 5:
            return [self._encode_segment(
                src, tmpl, ff, fp, env, appdir,
                dur, prefix, 1, 1, base_name=src)]

        n_parts = int(dur // SEGMENT_SEC)
        if dur - n_parts * SEGMENT_SEC > 2:
            n_parts += 1

        outputs = []
        for i in range(n_parts):
            start = i * SEGMENT_SEC
            remain = min(SEGMENT_SEC, dur - start)
            if remain < 2:
                break
            pfx = '%sParc %d/%d: ' % (prefix, i + 1, n_parts)
            part = os.path.join(appdir, '_part_%d.mp4' % i)
            self._set_status('%sKesiliyor...' % pfx)
            self._cut_segment(ff, src, start, remain, part, env)
            try:
                out = self._encode_segment(
                    part, tmpl, ff, fp, env, appdir,
                    remain, pfx, i + 1, n_parts, base_name=src)
                outputs.append(out)
            finally:
                try:
                    os.remove(part)
                except OSError:
                    pass
        return outputs

    def _batch_worker(self):
        core.clear_cancel()
        keep_screen_on()
        total = len(self.queue)
        done, failed = [], []
        try:
            for i, src in enumerate(self.queue, 1):
                if core.is_cancelled():
                    break
                try:
                    outs = self._process_one(src, i, total)
                    if outs:
                        done.extend(outs)
                except Exception as e:
                    msg = str(e)
                    if 'Iptal' in msg or core.is_cancelled():
                        break
                    print('HATA (%s): %s' % (src, msg))
                    failed.append((src, msg[:80]))

            if core.is_cancelled():
                self._set_status('Iptal edildi')
                self._set_info('%d/%d tamamlandi' % (len(done), total))
            elif failed:
                self._set_status('Kismi tamam (%d/%d)' % (len(done), total))
                self._set_info('Hatalar: ' + '; '.join(
                    os.path.basename(s) for s, _ in failed[:3]))
            else:
                self._set_progress(1.0)
                self._set_status('Tamamlandi: %d video' % len(done))
                if done:
                    self._set_info(os.path.basename(done[-1]))
                    send_notification(
                        'CMR35 - Tamamlandi',
                        '%d video donusturuldu' % len(done))
                    if len(done) == 1:
                        self._share(done[0])
        except Exception as e:
            self._set_status('Hata')
            self._set_info(str(e)[:150])
        finally:
            self._set_busy(False)
            self._set_canceling(False)


class CMR35App(App):
    def build(self):
        Builder.load_string(KV)
        return Root()


if __name__ == '__main__':
    CMR35App().run()
