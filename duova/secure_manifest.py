from pathlib import Path
import re
root=Path('.')
allowed={'android.permission.INTERNET','android.permission.ACCESS_NETWORK_STATE','android.permission.ACCESS_WIFI_STATE','android.permission.WAKE_LOCK','android.permission.VIBRATE','android.permission.FOREGROUND_SERVICE'}
for rel in ['Bcore/src/main/AndroidManifest.xml','app/src/main/AndroidManifest.xml']:
 p=root/rel
 s=p.read_text()
 s=re.sub(r'<uses-permission\b[^>]*android:name="([^"]+)"[^>]*/>',lambda m:m.group(0) if m.group(1) in allowed or (rel.startswith('app/') and m.group(1)=='android.permission.QUERY_ALL_PACKAGES') else '',s,flags=re.S)
 found=set()
 def dedup(m):
  key=re.search(r'android:name="([^"]+)"',m.group(0)).group(1)
  if key in found:return ''
  found.add(key);return m.group(0)
 s=re.sub(r'<uses-permission\b[^>]*/>',dedup,s,flags=re.S)
 if rel.startswith('app/'):
  s=s.replace('android:allowBackup="true"','android:allowBackup="false"')
  if 'tools:replace="android:allowBackup"' not in s:s=s.replace('<application','<application tools:replace="android:allowBackup"',1)
  s=s.replace('<application','<application android:usesCleartextTraffic="false"',1)
  s=s.replace('tools:replace="android:allowBackup"','tools:replace="android:allowBackup,android:usesCleartextTraffic"')
 p.write_text(s)
p=root/'app/src/main/res/xml/network_security_config.xml'
p.write_text('<?xml version="1.0" encoding="utf-8"?><network-security-config><base-config cleartextTrafficPermitted="false"/></network-security-config>')
p=root/'app/src/main/res/values/themes.xml';p.write_text(p.read_text().replace('name="colorBackground"','name="android:colorBackground"'))
p=root/'app/src/main/res/menu/menu_main.xml';s=p.read_text()
if '@+id/main_tg' not in s:s=s.replace('</menu>','<item android:id="@+id/main_tg" android:title="Community" android:visible="false"/></menu>')
p.write_text(s)
print('Permissions hardening complete')
