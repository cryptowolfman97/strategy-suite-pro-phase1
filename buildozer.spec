[app]

title = Strategy Suite Pro v7 by SHV
package.name = strategysuiteprobyshvv7
package.domain = org.sachith

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,json,pem

version = 7

requirements = python3,kivy,requests,certifi,rsa,pyasn1

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.accept_sdk_license = True

android.api = 33
android.minapi = 21

log_level = 2

[buildozer]
log_level = 2
warn_on_root = 0
