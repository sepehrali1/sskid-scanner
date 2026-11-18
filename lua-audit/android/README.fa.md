# Sskid Script Scanner — نسخهٔ اندروید (APK)

این پوشه یک پروژهٔ استاندارد اندروید است که **همان اسکنر** را داخل یک
`WebView` نشان می‌دهد. کل منطق اسکن داخل فایل تک‌فایلی
`app/src/main/assets/SskidScanner.html` است (همان خروجی `web/build_web.py`).

> ⚠️ صادقانه: این APK موتور پایتون را «بازنویسی» نمی‌کند؛ همان اپ وب
> (پورت‌شدهٔ موتور به JavaScript) را در پوستهٔ اندروید اجرا می‌کند.
> نتایج با نسخهٔ پایتون کاملاً یکسان تست شده‌اند (md5/sha1/sha256/آنتروپی/امتیاز/حکم).

## ساخت APK — سه راه

### ۱) ابری با GitHub Actions (پیشنهادی، همین حالا کار می‌کند)

سرورهای گوگل از این سیستم بلاک‌اند، ولی از رانرهای گیت‌هاب نه.

1. کل پوشهٔ پروژه (`lua-audit` و `.github`) را در یک مخزن گیت‌هاب push کن.
2. تب **Actions** → ورک‌فلوی **Build Android APK** → **Run workflow**.
3. بعد از چند دقیقه، APK را از بخش **Artifacts** همان اجرا دانلود کن
   (نام: `SskidScriptScanner-apk`).
4. برای انتشار: یک تگ بزن (`git tag v1.0 && git push origin v1.0`) تا APK
   خودکار به صفحهٔ **Releases** هم ضمیمه شود.

فایل ورک‌فلو: `.github/workflows/build-apk.yml`

### ۲) ساخت محلی (اگر Android SDK داری)

```powershell
# پیش‌نیاز: JDK 17، Android SDK (متغیر ANDROID_HOME)، Python + Pillow
cd lua-audit\android
.\build_apk.ps1
# خروجی: app\build\outputs\apk\debug\app-debug.apk
```

### ۳) دستی با Android Studio

پوشهٔ `lua-audit/android` را با Android Studio باز کن (Open an existing project)
و **Build → Build Bundle(s)/APK(s) → Build APK(s)** را بزن.

## امضای نسخهٔ release (اختیاری)

APK دیباگ خودش امضاشده و روی گوشی نصب می‌شود. اگر APK release امضاشده
می‌خواهی، این Secrets را در مخزن بگذار و ورک‌فلو خودش می‌سازد:

| Secret | توضیح |
|---|---|
| `KEYSTORE_BASE64` | فایل keystore به‌صورت base64 |
| `KEYSTORE_PASSWORD` | رمز keystore |
| `KEY_ALIAS` | نام کلید |
| `KEY_PASSWORD` | رمز کلید |

ساخت keystore:

```bash
keytool -genkeypair -v -keystore sskid.keystore -alias sskid \
        -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 sskid.keystore     # خروجی را در KEYSTORE_BASE64 بگذار
```

## ساختار

```
android/
├─ settings.gradle, build.gradle, gradle.properties
├─ gradlew, gradlew.bat, gradle/wrapper/…        (Gradle 8.7)
├─ build_apk.ps1                                 (اسکریپت ساخت محلی)
├─ make_icons.py                                 (ساخت آیکون‌های لانچر از assets/logo.png)
└─ app/
   ├─ build.gradle                               (AGP 8.5.2، compileSdk 34، minSdk 24)
   └─ src/main/
      ├─ AndroidManifest.xml
      ├─ java/com/sskid/scanner/MainActivity.java
      ├─ assets/SskidScanner.html               (تولیدشده — commit نمی‌شود)
      └─ res/mipmap-*/ic_launcher.png           (تولیدشده — commit نمی‌شود)
```

## نکتهٔ امنیتی

مجوز تنها `INTERNET` است و آن هم فقط برای تب **«اسلات‌های آنلاین»**
(چک کردن هش دو فایل شناخته‌شده). خودِ اسکن هیچ فایلی را اجرا یا دانلود نمی‌کند.
