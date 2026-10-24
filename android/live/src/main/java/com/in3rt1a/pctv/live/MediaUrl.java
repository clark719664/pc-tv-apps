package com.in3rt1a.pctv.live;

import java.net.URI;
import java.util.Locale;

/** Only public HTTPS stream locations may cross the native playback boundary. */
public final class MediaUrl {
    public static boolean allowed(String text) {
        if (text == null || text.length() > 8192) return false;
        try {
            URI uri = new URI(text);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null || uri.getUserInfo() != null) return false;
            host = host.toLowerCase(Locale.ROOT);
            if (host.equals("localhost") || host.endsWith(".localhost") || host.endsWith(".local") || host.endsWith(".internal")) return false;
            // Public catalogues use DNS names; exclude literal addresses and single-label names.
            return host.contains(".") && !host.matches("[0-9.]+") && !host.contains(":") && !host.contains("[");
        } catch (Exception invalid) { return false; }
    }
    private MediaUrl() {}
}
