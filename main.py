# -*- coding: utf-8 -*-
import os, threading, shutil
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.utils import platform

import cmr35_core as core


# ============================================================
# IZINLER
# ============================================================
def request_permissions():
    """Aciklamada Android surumune gore izin ister."""
    if platform != 'android':
        return
    try:
        from jnius import autoclass, cast
        from android.permissions import request_permissions as rp, Permission

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        act = PythonActivity.mActivity
        Build = autoclass('android.os.Build$VERSION')
        sdk = Build.SDK_INT

        perms = []
        if sdk >= 33:
            perms = [Permission.READ_MEDIA_VIDEO]
        elif sdk >= 23:
            perms = [Permission.READ_EXTERNAL_STORAGE]
            if sdk < 30:
                perms.append(Permission.WRITE_EXTERNAL_STORAGE)
        if perms:
            rp(perms)

        # Android 11+ icin "Tum dosyalara erisim" ayar sayfasi
        if sdk >= 30:
            Clock.schedule_once(
                lambda dt: _open_all_files_settings(), 1.5)
    except Exception as e:
        print('izin hata:', e)


def _open_all_files_settings():
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Settings = autoclass('android.provider.Settings')
        Uri = autoclass('android.net.Uri')
        Build = autoclass('android.os.Build$VERSION')

        act = PythonActivity.mActivity
        if Build.SDK_INT < 30:
            return

        # Zaten izinli mi?
        Environment = autoclass('android.os.Environment')
        if Environment.isExternalStorageManager():
            print('MANAGE_EXTERNAL_STORAGE zaten verilmis')
            return

        pkg = act.getPackageName()
        intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
        intent.setData(Uri.parse('package:' + pkg))
        act.startActivity(intent)
    except Exception as e:
        print('settings hata:', e)


# ============================================================
# YARDIMCILAR
# ============================================================
def human_size(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return '%.1f %s' % (n, u)
        n /= 1024
    return '%.1f TB' % n


def extract_ffmpeg():
    """APK assets'ten ffmpeg/ffprobe/MOV00028 cikar."""
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
    """Paylasimla gelen videoyu al. Birden fazla API dener."""
    if platform != 'android':
        return None
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Build = autoclass('android.os.Build$VERSION')
        act = PythonActivity.mActivity
        intent = act.getIntent()
        if intent is None:
            print('SHARE: intent yok')
            return None
        action = intent.getAction()
        print('SHARE: action=', action)
        if action != Intent.ACTION_SEND:
            return None

        uri = None
        # Android 13+ icin yeni API
        try:
            Parcelable = autoclass('android.os.Parcelable')
            uri = intent.getParcelableExtra(Intent.EXTRA_STREAM, Parcelable)
        except Exception as e:
            print('SHARE: yeni API hata:', e)
        # Eski API fallback
        if uri is None:
            try:
                uri = intent.getParcelableExtra(Intent.EXTRA_STREAM)
            except Exception as e:
                print('SHARE: eski API hata:', e)
        if uri is None:
            print('SHARE: uri yok')
            return None
        print('SHARE: uri=', str(uri))

        # App-ozel klasore kopyala (izin gerekmez)
        bindir = os.path.join(act.getFilesDir().getAbsolutePath(), 'shared')
        os.makedirs(bindir, exist_ok=True)
        import time as _t
        dst = os.path.join(bindir, 'shared_%d.mp4' % int(_t.time()))

        resolver = act.getContentResolver()
        stream = resolver.openInputStream(uri)
        if stream is None:
            print('SHARE: stream yok')
            return None
        buf = bytearray(65536)
        total = 0
        with open(dst, 'wb') as out:
            while True:
                n = stream.read(buf)
                if n <= 0:
                    break
                out.write(bytes(buf[:n]))
                total += n
        stream.close()
        print('SHARE: kopyalandi', dst, total)
        return dst
    except Exception as e:
        print('SHARE hata:', e)
        return None



# ============================================================
# ARAYUZ
# ============================================================
KV = '''
<Root>:
    orientation: 'vertical'
    padding: dp(18)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: 0.07, 0.07, 0.09, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: 'CMR35'
        font_size: '32sp'
        bold: True
        color: 0.16, 0.82, 0.44, 1
        size_hint_y: None
        height: dp(40)
    Label:
        text: 'Video  →  Kamera AVI dönüştürücü'
        font_size: '12sp'
        color: 0.55, 0.55, 0.62, 1
        size_hint_y: None
        height: dp(18)

    Widget:
        size_hint_y: None
        height: dp(10)

    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(130)
        padding: dp(16), dp(12)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: 0.13, 0.13, 0.16, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(14)]
        Label:
            text: root.status
            font_size: '16sp'
            bold: True
            color: 1, 1, 1, 1
            size_hint_y: None
            height: dp(28)
            text_size: self.width, None
            halign: 'center'
        Label:
            text: root.info
            font_size: '11sp'
            color: 0.62, 0.62, 0.68, 1
            text_size: self.width, None
            halign: 'center'
            valign: 'top'

    ProgressBar:
        max: 1.0
        value: root.progress
        size_hint_y: None
        height: dp(8)

    Widget:
        size_hint_y: None
        height: dp(6)

    Button:
        text: '📂   Video Seç'
        font_size: '16sp'
        bold: True
        color: 1, 1, 1, 1
        size_hint_y: None
        height: dp(62)
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
                radius: [dp(14)]
        on_release: root.pick()

    Button:
        text: '▶   Dönüştür' if not root.busy else '⏳   Dönüştürülüyor...'
        font_size: '16sp'
        bold: True
        color: 1, 1, 1, 1
        size_hint_y: None
        height: dp(62)
        background_normal: ''
        background_disabled_normal: ''
        background_color: 0, 0, 0, 0
        disabled: (not root.src) or root.busy
        canvas.before:
            Color:
                rgba: (1, 0.45, 0, 1) if (not self.disabled) else (0.35, 0.35, 0.38, 1)
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(14)]
        on_release: root.start()

    Widget:
'''


class Root(BoxLayout):
    status = StringProperty('İzin kontrol ediliyor...')
    info = StringProperty('Lütfen bekleyin')
    progress = NumericProperty(0.0)
    src = StringProperty('')
    busy = BooleanProperty(False)

    def on_kv_post(self, base_widget):
        # Arayuz hazir olunca izinleri iste
        Clock.schedule_once(lambda dt: self._ask_permissions(), 0.4)

    def _ask_permissions(self):
        try:
            request_permissions()
            Clock.schedule_once(lambda dt: self._after_perms(), 3.0)
        except Exception as e:
            print('perms hata:', e)
            self._after_perms()

    def _after_perms(self):
        self.status = 'Hazır'
        self.info = 'Dönüştürmek için video seçin'
        # Paylasimla gelen video var mi?
        try:
            path = import_shared_video()
            if path and os.path.isfile(path):
                self.src = path
                size = human_size(os.path.getsize(path))
                self.status = 'Paylaşılan video hazır'
                self.info = '%s\n%s' % (os.path.basename(path), size)
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

    def _template_path(self):
        try:
            from jnius import autoclass
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            bindir = os.path.join(act.getFilesDir().getAbsolutePath(), 'bin')
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

    def on_resume(self):
        # Uygulama one geldiginde paylasim geldi mi kontrol et
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            act = PythonActivity.mActivity
            intent = act.getIntent()
            if intent and intent.getAction() == Intent.ACTION_SEND:
                p = import_shared_video()
                if p and os.path.isfile(p):
                    self.src = p
                    size = human_size(os.path.getsize(p))
                    self.status = 'Paylasilan video hazir'
                    self.info = '%s\n%s' % (os.path.basename(p), size)
                    # Intent'i temizle ki tekrar tetiklenmesin
                    try:
                        intent.setAction('')
                        act.setIntent(intent)
                    except Exception:
                        pass
        except Exception as e:
            print('on_resume hata:', e)

    def pick(self):
        box = BoxLayout(orientation='vertical')
        fc = FileChooserListView(
            path=self._best_dir(),
            filters=['*.mp4', '*.mkv', '*.mov', '*.avi', '*.webm',
                     '*.m4v', '*.3gp', '*.ts'])
        box.add_widget(fc)
        pop = Popup(title='Video Seç', content=box,
                    size_hint=(0.95, 0.95))

        def _go(*a):
            if fc.selection:
                self.src = fc.selection[0]
                try:
                    size = human_size(os.path.getsize(self.src))
                except OSError:
                    size = '?'
                self.status = 'Video hazır'
                self.info = '%s\n%s' % (os.path.basename(self.src), size)
            pop.dismiss()

        btn = Button(text='Seç', size_hint_y=None, height='48dp')
        btn.bind(on_release=_go)
        box.add_widget(btn)
        pop.open()

    def start(self):
        if not self.src or self.busy:
            return
        self.busy = True
        self.status = 'Başlıyor...'
        self.progress = 0.0
        threading.Thread(target=self._work, daemon=True).start()

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
                Intent.createChooser(i, 'Paylaş'))
        except Exception:
            pass

    def _work(self):
        try:
            extract_ffmpeg()
            ff, fp, libdir = core.find_ffmpeg()
            if not ff or not fp:
                self._set_status('❌  ffmpeg bulunamadı')
                self._set_info('Uygulamayı yeniden kurun')
                return

            env = core._env_with_libs(libdir)
            tmpl = self._template_path()
            if not tmpl:
                self._set_status('❌  Şablon bulunamadı')
                self._set_info('MOV00028.AVI /sdcard/Download\'a kopyalayın')
                return

            appdir = self._app_dir()
            norm = os.path.join(appdir, 'norm.avi')
            outtmp = os.path.join(appdir, 'out.avi')

            dur = core.probe_duration(fp, self.src, env)
            mins = int(dur // 60)
            secs = int(dur % 60)
            self._set_status('Video: %ddk %dsn' % (mins, secs))
            self._set_info('Encode ediliyor...')

            def prog(sec, total):
                if total > 0:
                    Clock.schedule_once(lambda *_: setattr(
                        self, 'progress', min(0.98, sec / total)))

            core.normalize_input(ff, fp, self.src, norm, dur,
                                 env=env, on_progress=prog)
            self._set_status('AVI inşa ediliyor...')
            Clock.schedule_once(lambda *_: setattr(self, 'progress', 0.99))
            core.build_output(tmpl, norm, outtmp)

            out = self.src.rsplit('.', 1)[0] + '_CMR35.AVI'
            try:
                shutil.move(outtmp, out)
            except Exception:
                out = outtmp
            try:
                os.remove(norm)
            except OSError:
                pass

            mb = os.path.getsize(out) / (1024 * 1024)
            Clock.schedule_once(lambda *_: setattr(self, 'progress', 1.0))
            self._set_status('✓  Tamamlandı')
            self._set_info('%s\n%.1f MB' % (os.path.basename(out), mb))
            self._share(out)
        except Exception as e:
            self._set_status('❌  Hata')
            self._set_info(str(e)[:150])
        finally:
            self._set_busy(False)


class CMR35App(App):
    def build(self):
        Builder.load_string(KV)
        return Root()


if __name__ == '__main__':
    CMR35App().run()
