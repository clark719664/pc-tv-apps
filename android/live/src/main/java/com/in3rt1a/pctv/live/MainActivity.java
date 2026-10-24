package com.in3rt1a.pctv.live;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import android.widget.FrameLayout;
import java.io.ByteArrayInputStream;
import java.net.URLConnection;
import java.util.Collections;

public final class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private WebView browser;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        browser = new WebView(this);
        browser.setBackgroundColor(0xff0d0b16);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xff0d0b16);
        root.addView(browser, new FrameLayout.LayoutParams(-1, -1));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(root);
        WebSettings settings = browser.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSupportMultipleWindows(false);
        browser.addJavascriptInterface(new PlaybackBridge(), "PCTVPlayer");
        browser.setWebChromeClient(new WebChromeClient());
        browser.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (isLocal(url)) return false;
                if ("https".equals(url.getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, url)); }
                    catch (Exception unavailable) { Toast.makeText(MainActivity.this, "No browser is available to open this link.", Toast.LENGTH_LONG).show(); }
                }
                return true;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (!HOST.equals(url.getHost())) return null;
                String path = url.getPath();
                if (!isLocal(url) || path == null || path.contains("..") || path.contains("\\")) return missing();
                if (path.equals("/")) path = "/index.html";
                try {
                    String mime = URLConnection.guessContentTypeFromName(path);
                    if (path.endsWith(".js") || path.endsWith(".mjs")) mime = "text/javascript";
                    if (path.endsWith(".css")) mime = "text/css";
                    if (path.endsWith(".json") || path.endsWith(".webmanifest")) mime = "application/json";
                    if (mime == null) mime = "application/octet-stream";
                    return new WebResourceResponse(mime, "UTF-8", 200, "OK", Collections.singletonMap(
                            "Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self' https:; media-src https: blob:; worker-src 'self' blob:; frame-src 'none'; object-src 'none'; base-uri 'self'"), getAssets().open(path.substring(1)));
                } catch (Exception missing) { return missing(); }
            }
        });
        browser.loadUrl("https://" + HOST + "/index.html");
    }

    private static boolean isLocal(Uri uri) { return "https".equals(uri.getScheme()) && HOST.equals(uri.getHost()) && uri.getPort() == -1; }
    private static WebResourceResponse missing() {
        return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
    }
    private final class PlaybackBridge {
        @JavascriptInterface public void play(String url, String title) {
            if (!MediaUrl.allowed(url)) return;
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed() || !isLocal(Uri.parse(browser.getUrl() == null ? "" : browser.getUrl()))) return;
                startActivity(new Intent(MainActivity.this, PlayerActivity.class)
                        .putExtra("url", url).putExtra("title", title == null ? "Live TV" : title.substring(0, Math.min(160, title.length()))));
            });
        }
    }
    @Override protected void onResume() { super.onResume(); if (browser != null) browser.onResume(); }
    @Override protected void onPause() { if (browser != null) browser.onPause(); super.onPause(); }
    @Override protected void onDestroy() { if (browser != null) { browser.removeJavascriptInterface("PCTVPlayer"); browser.destroy(); } super.onDestroy(); }
}
