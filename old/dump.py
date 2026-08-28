import zipfile
import re

apk_file = "0_LCW_RCcar_1.0.3.apk"
js_file = "assets/apps/__UNI__824E576/www/app-service.js"

with zipfile.ZipFile(apk_file, 'r') as z:
    code = z.read(js_file).decode('utf-8', errors='ignore')

print("=" * 60)
print("1. ALL REGISTERED VUE PAGES & COMPONENTS")
print("=" * 60)
for p in set(re.findall(r'pages/[\w/]+|components/[\w/]+', code)):
    print(f"  - {p}")

print("\n" + "=" * 60)
print("2. ALL STORAGE KEYS & CONFIG SETTINGS")
print("=" * 60)
for k in set(re.findall(r'getStorageSync\(["\'](\w+)["\']\)|setStorageSync\(["\'](\w+)["\']', code)):
    key = k[0] or k[1]
    print(f"  - Key: '{key}'")

print("\n" + "=" * 60)
print("3. AUDIO / SFX ASSETS")
print("=" * 60)
for a in set(re.findall(r'/static/[\w-]+\.(?:wav|mp3|png|jpg)', code)):
    print(f"  - {a}")

print("\n" + "=" * 60)
print("4. ALL COMMAND / PROTOCOL STRING TEMPLATES")
print("=" * 60)
for t in set(re.findall(r'["\'](aa00[\w]+)["\']', code, re.IGNORECASE)):
    print(f"  - Hex Template: {t}")