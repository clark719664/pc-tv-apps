package com.in3rt1a.pctv.live;

import android.app.Activity;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.MediaController;
import android.widget.TextView;
import android.widget.VideoView;

public final class PlayerActivity extends Activity {
    private VideoView video;
    private TextView message;
    private Button retry;
    private String url;
    private final Handler timer = new Handler(Looper.getMainLooper());
    private final Runnable timeout = () -> fail("This channel did not start. It may be offline or unavailable in your region. Try another channel.");

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        url = getIntent().getStringExtra("url");
        if (!MediaUrl.allowed(url)) { finish(); return; }
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        Button back = new Button(this);
        back.setText("Back to channels");
        back.setOnClickListener(v -> finish());
        root.addView(back);
        TextView title = new TextView(this);
        title.setText(getIntent().getStringExtra("title")); title.setTextColor(Color.WHITE); title.setTextSize(22); title.setPadding(20, 8, 20, 8);
        root.addView(title);
        FrameLayout frame = new FrameLayout(this);
        root.addView(frame, new LinearLayout.LayoutParams(-1, 0, 1));
        video = new VideoView(this);
        frame.addView(video, new FrameLayout.LayoutParams(-1, -1, Gravity.CENTER));
        message = new TextView(this);
        message.setTextColor(Color.WHITE); message.setGravity(Gravity.CENTER); message.setPadding(28, 16, 28, 16);
        root.addView(message);
        retry = new Button(this); retry.setText("Retry channel"); retry.setOnClickListener(v -> play()); root.addView(retry);
        MediaController controls = new MediaController(this); controls.setAnchorView(video); video.setMediaController(controls);
        video.setOnPreparedListener(player -> { timer.removeCallbacks(timeout); message.setText(""); retry.setVisibility(View.GONE); video.start(); });
        video.setOnErrorListener((player, what, extra) -> { fail("This stream cannot play right now. It may be offline, region restricted, or use an unsupported format. Try another channel."); return true; });
        video.setOnCompletionListener(player -> fail("This live stream ended. Retry or choose another channel."));
        setContentView(root);
    }
    @Override protected void onStart() { super.onStart(); if (video != null) play(); }
    private void play() {
        timer.removeCallbacks(timeout); video.stopPlayback(); retry.setVisibility(View.GONE); message.setText("Connecting to channel…");
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        video.setVideoURI(Uri.parse(url)); video.start(); timer.postDelayed(timeout, 25000);
    }
    private void fail(String text) {
        timer.removeCallbacks(timeout); if (video != null) video.stopPlayback();
        message.setText(text); retry.setVisibility(View.VISIBLE); getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
    @Override protected void onStop() { timer.removeCallbacksAndMessages(null); if (video != null) video.stopPlayback(); super.onStop(); }
}
