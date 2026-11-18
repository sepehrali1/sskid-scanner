package com.sskid.scanner;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;

/**
 * Sskid Script Scanner — Android shell.
 *
 * تمام منطق اسکنر داخل فایل آفلاین assets/SskidScanner.html است.
 * این Activity فقط آن را در یک WebView بار می‌کند. هیچ فایلی از اینترنت
 * بار نمی‌شود و هیچ اسکریپتی اجرا/دانلود نمی‌شود.
 */
public class MainActivity extends Activity {

    private WebView web;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);      // موتور اسکنر JS است
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);        // خواندن از android_asset
        s.setAllowContentAccess(false);
        s.setSupportZoom(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setLoadWithOverviewMode(false);
        s.setUseWideViewPort(true);

        web.setBackgroundColor(0xFF07070B); // رنگ پس‌زمینهٔ تم
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.loadUrl("file:///android_asset/SskidScanner.html");

        setContentView(web);
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
