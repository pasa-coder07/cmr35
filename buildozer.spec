[app]
p4a.branch = develop
title = CMR35
package.name = cmr35
package.domain = com.cmr35
source.dir = .
source.include_exts = py,kv,avi,so
source.include_patterns = assets/*,libs/arm64-v8a/*
source.exclude_dirs = bin,.buildozer,__pycache__

version = 1.0
requirements = python3,kivy,pyjnius,android

orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_VIDEO
android.archs = arm64-v8a
android.minapi = 24
android.api = 33
android.build_tools_version = 33.0.2
android.ndk = 25c
android.accept_sdk_license = True

android.add_libs_arm64_v8a = libs/arm64-v8a/*
android.add_assets = assets/MOV00028.AVI:assets/MOV00028.AVI

[buildozer]
log_level = 2
warn_on_root = 1
