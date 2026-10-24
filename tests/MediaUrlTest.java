import com.in3rt1a.pctv.live.MediaUrl;

public class MediaUrlTest {
    public static void main(String[] args) {
        String[] bad = {null, "", "http://media.example.com/a.m3u8", "file:///etc/passwd", "javascript:alert(1)", "https://localhost/a", "https://192.168.1.2/a", "https://127.0.0.1/a", "https://[::1]/a", "https://tv.local/a", "https://user:password@example.com/a", "https://server/a"};
        for (String url : bad) if (MediaUrl.allowed(url)) throw new AssertionError("Accepted: " + url);
        if (!MediaUrl.allowed("https://media.example.com/live.m3u8?token=abc%2F123")) throw new AssertionError("Rejected stream");
        System.out.println("PASS: 13 rejected URLs and 1 valid HTTPS stream");
    }
}
