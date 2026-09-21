# -*- coding: utf-8 -*-
import os, threading, shutil
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.utils import platform

import cmr35_core as core




def import_shared_video():
    """Paylasimla gelen videoyu al, /sdcard/Download'a kopyala."""
    if platform != 'android':
        return None
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        File = autoclass('java.io.File')
        FileOutputStream = autoclass('java.io.FileOutputStream')
        InputStream = autoclass('java.io.InputStream')
        act = PythonActivity.mActivity
        intent = act.getIntent()
        if intent is None:
            return None
        action = intent.getAction()
        if action != Intent.ACTION_SEND:
            return None
        uri = intent.getParcelableExtra(Intent.EXTRA_STREAM)
        if uri is None:
            return None
        resolver = act.getContentResolver()
        stream = resolver.openInputStream(uri)
        # /sdcard/Download/ klasorune kopyala
        dst_dir = '/sdcard/Download'
        import time as _t
        dst = os.path.join(dst_dir, 'shared_%d.mp4' % int(_t.time()))
        buf = bytearray(65536)
        with open(dst, 'wb') as out:
            while True:
                n = stream.read(buf)
                if n <= 0:
                    break
                out.write(bytes(buf[:n]))
        stream.close()
        print('shared video alindi:', dst)
        return dst
    except Exception as e:
        print('shared video hata:', e)
        return None

def extract_ffmpeg():
    return  # ARTIK GEREKSIZ - statik ffmpeg native lib
    """APK assets'ten ffmpeg/ffprobe cikar, calistirilabilir yap."""
    if platform != 'android':
        return
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        act = PythonActivity.mActivity
        files_dir = act.getFilesDir().getAbsolutePath()
        bindir = os.path.join(files_dir, 'bin')
        os.makedirs(bindir, exist_ok=True)
        assets = act.getAssets()
        for name in ('ffmpeg', 'ffprobe', 'MOV00028.AVI'):
            target = os.path.join(bindir, name)
            if os.path.exists(target) and os.path.getsize(target) > 1000:
                continue
            try:
                istream = assets.open('bin/' + name)
            except Exception as e:
                print('asset acilamadi:', name, e)
                continue
            with open(target, 'wb') as out:
                buf = bytearray(65536)
                while True:
                    n = istream.read(buf)
                    if n <= 0:
                        break
                    out.write(bytes(buf[:n]))
            istream.close()
            os.chmod(target, 0o755)
            print('extracted:', target, os.path.getsize(target))
    except Exception as e:
        print('extract_ffmpeg hata:', e)


KV = '''
<Root>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(8)
    Label:
        text: 'CMR35 MOBIL'
        font_size: '22sp'
        bold: True
        size_hint_y: None
        height: dp(36)
    Label:
        text: root.status
        size_hint_y: None
        height: dp(30)
        text_size: self.width, None
        halign: 'center'
    ProgressBar:
        max: 1.0
        value: root.progress
        size_hint_y: None
        height: dp(24)
    Button:
        text: 'Video Sec'
        size_hint_y: None
        height: dp(56)
        on_release: root.pick()
    Button:
        text: 'Donustur'
        size_hint_y: None
        height: dp(56)
        disabled: not root.src
        on_release: root.start()
    Label:
        text: root.info
        size_hint_y: None
        height: dp(80)
        text_size: self.width, None
        halign: 'center'
        valign: 'middle'
        font_size: '12sp'
'''


class Root(BoxLayout):
    status = StringProperty('Hazir')
    info = StringProperty('')
    progress = NumericProperty(0.0)
    src = StringProperty('')

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

    def _template_path(self):
        # 1) extract edilmis (APK assets'ten)
        try:
            from jnius import autoclass
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            bindir = os.path.join(act.getFilesDir().getAbsolutePath(), 'bin')
            p = os.path.join(bindir, 'MOV00028.AVI')
            if os.path.isfile(p):
                return p
        except Exception:
            pass
        # 2) /sdcard fallback
        for d in ['/sdcard/Download', '/sdcard',
                  '/storage/emulated/0/Download']:
            p = os.path.join(d, 'MOV00028.AVI')
            if os.path.isfile(p):
                return p
        return None


    def pick(self):
        box = BoxLayout(orientation='vertical')
        fc = FileChooserListView(
            path=self._best_dir(),
            filters=['*.mp4', '*.mkv', '*.mov', '*.avi', '*.webm',
                     '*.m4v', '*.3gp', '*.ts'])
        box.add_widget(fc)
        pop = Popup(title='Video Sec', content=box,
                    size_hint=(0.95, 0.95))

        def _go(*a):
            if fc.selection:
                self.src = fc.selection[0]
                self.info = self.src
                self.status = 'Video hazir'
            pop.dismiss()

        btn = Button(text='Sec', size_hint_y=None, height='48dp')
        btn.bind(on_release=_go)
        box.add_widget(btn)
        pop.open()

    def on_start(self):
        """Uygulama acildiginda paylasimla gelen video var mi kontrol et."""
        try:
            path = import_shared_video()
            if path and os.path.isfile(path):
                self.src = path
                self.info = path
                self.status = 'Paylasilan video hazir'
        except Exception as e:
            print('on_start hata:', e)

    def start(self):
        if not self.src:
            return
        self.status = 'Basliyor...'
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
                Intent.createChooser(i, 'Paylas'))
        except Exception:
            pass

    def _work(self):
        try:
            extract_ffmpeg()
            ff, fp, libdir = core.find_ffmpeg()
            if not ff or not fp:
                self._set_status('ffmpeg bulunamadi')
                return
            env = core._env_with_libs(libdir)
            tmpl = self._template_path()
            if not tmpl:
                self._set_status('Sablon MOV00028.AVI yok')
                return

            appdir = self._app_dir()
            norm = os.path.join(appdir, 'norm.avi')
            outtmp = os.path.join(appdir, 'out.avi')

            dur = core.probe_duration(fp, self.src, env)
            self._set_status('Encode: %ddk %dsn' %
                             (int(dur // 60), int(dur % 60)))

            def prog(sec, total):
                if total > 0:
                    Clock.schedule_once(lambda *_: setattr(
                        self, 'progress', min(1.0, sec / total)))

            core.normalize_input(ff, fp, self.src, norm, dur,
                                 env=env, on_progress=prog)
            self._set_status('AVI insa ediliyor...')
            self.progress = 0.99
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
            self.progress = 1.0
            self._set_status('Bitti: %.1f MB' % mb)
            self._share(out)
        except Exception as e:
            self._set_status('HATA: ' + str(e)[:140])


class CMR35App(App):
    def build(self):
        Builder.load_string(KV)
        self.root_widget = Root()
        return self.root_widget

    def on_start(self):
        Clock.schedule_once(lambda dt: self.root_widget.on_start(), 0.5)


if __name__ == '__main__':
    CMR35App().run()
