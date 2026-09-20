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

KV = '''
<Root>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(8)
    Label:
        text: 'CMR35 MOBIL'
        font_size: '20sp'
        bold: True
        size_hint_y: None
        height: dp(32)
    Label:
        text: root.status
        size_hint_y: None
        height: dp(28)
        text_size: self.width, None
        halign: 'center'
    ProgressBar:
        max: 1.0
        value: root.progress
        size_hint_y: None
        height: dp(20)
    Button:
        text: 'Video Sec'
        size_hint_y: None
        height: dp(48)
        on_release: root.pick()
    Button:
        text: 'Donustur'
        size_hint_y: None
        height: dp(48)
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
        for d in ['/sdcard/Download','/storage/emulated/0/Download',
                  '/sdcard/Movies','/storage/emulated/0/Movies',
                  '/sdcard/DCIM','/sdcard']:
            if os.path.isdir(d):
                return d
        return '/sdcard' if os.path.isdir('/sdcard') else os.path.expanduser('~')

    def _app_dir(self):
        try:
            from android.storage import app_storage_path
            return app_storage_path()
        except Exception:
            return os.path.expanduser('~')

    def pick(self):
        box = BoxLayout(orientation='vertical')
        fc = FileChooserListView(
            path=self._best_dir(),
            filters=['*.mp4','*.mkv','*.mov','*.avi','*.webm','*.m4v','*.3gp','*.ts'])
        box.add_widget(fc)
        pop = Popup(title='Video Sec', content=box, size_hint=(0.95, 0.95))
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

    def start(self):
        if not self.src:
            return
        self.status = 'Basliyor...'
        self.progress = 0.0
        threading.Thread(target=self._work, daemon=True).start()

    def _set_status(self, msg):
        Clock.schedule_once(lambda *_: setattr(self, 'status', msg))

    def _template_path(self):
        base = self._app_dir()
        for d in [base, os.path.dirname(os.path.abspath(__file__))]:
            p = os.path.join(d, 'MOV00028.AVI')
            if os.path.isfile(p):
                return p
        for d in ['/sdcard/Download', '/sdcard', '/storage/emulated/0/Download']:
            p = os.path.join(d, 'MOV00028.AVI')
            if os.path.isfile(p):
                return p
        return None

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
            i.putExtra(Intent.EXTRA_STREAM, cast('android.os.Parcelable', u))
            PythonActivity.mActivity.startActivity(Intent.createChooser(i, 'Paylas'))
        except Exception:
            pass

    def _work(self):
        try:
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
            self._set_status('Encode: %d dk %d sn' % (int(dur // 60), int(dur % 60)))
            def prog(sec, total):
                if total > 0:
                    Clock.schedule_once(lambda *_: setattr(
                        self, 'progress', min(1.0, sec / total)))
            core.normalize_input(ff, fp, self.src, norm, dur, env=env, on_progress=prog)
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
            size_mb = os.path.getsize(out) / (1024 * 1024)
            self.progress = 1.0
            self._set_status('Bitti: %.1f MB' % size_mb)
            self._share(out)
        except Exception as e:
            self._set_status('HATA: ' + str(e)[:140])

class CMR35App(App):
    def build(self):
        Builder.load_string(KV)
        return Root()

if __name__ == '__main__':
    CMR35App().run()
