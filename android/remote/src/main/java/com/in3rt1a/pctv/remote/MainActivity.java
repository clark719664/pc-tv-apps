package com.in3rt1a.pctv.remote;

import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.*;
import android.net.wifi.WifiManager;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.*;
import java.lang.ref.WeakReference;
import java.net.Inet4Address;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    private static final int BG=0xff0d0b16, CARD=0xff1a1628, ORANGE=0xffff8a3d, MUTED=0xffb7afca;
    private static final String[] BRANDS={"roku","samsung","lg","vizio","googletv"};
    private static final String[] LABELS={"Roku","Samsung Tizen","LG webOS","Vizio SmartCast","Google TV / Android TV"};
    private static final ExecutorService WORKER=Executors.newSingleThreadExecutor();
    private static final Handler MAIN=new Handler(Looper.getMainLooper());
    private final List<View> controls=new ArrayList<>();
    private final List<JSONObject> saved=new ArrayList<>();
    private Spinner brands, televisions;
    private TextView status;
    private ProgressBar progress;
    private String selected="";
    private boolean busy, destroyed;
    private Network wifiNetwork;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        selected=getPreferences(MODE_PRIVATE).getString("selected","");
        buildUi(); submit("list",new JSONObject());
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private GradientDrawable surface(int color){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(16));return d;}
    private LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private TextView text(String value,int size,int color){TextView v=new TextView(this);v.setText(value);v.setTextSize(size);v.setTextColor(color);v.setPadding(0,dp(5),0,dp(5));return v;}
    private LinearLayout card(LinearLayout parent,String name){
        LinearLayout v=column();v.setPadding(dp(14),dp(12),dp(14),dp(14));v.setBackground(surface(CARD));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(14),0,0);parent.addView(v,p);
        TextView title=text(name,13,ORANGE);title.setTypeface(null,Typeface.BOLD);v.addView(title);return v;
    }
    private Button button(String label,Runnable action,boolean accent){
        Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextSize(14);b.setMinWidth(0);b.setMinimumWidth(0);
        b.setPadding(dp(4),dp(5),dp(4),dp(5));b.setTextColor(accent?BG:Color.WHITE);b.setBackground(surface(accent?ORANGE:0xff312943));
        b.setOnClickListener(v->action.run());controls.add(b);return b;
    }
    private void row(LinearLayout parent,Button... buttons){
        LinearLayout r=new LinearLayout(this);
        for(Button b:buttons){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(56),1);p.setMargins(dp(3),dp(4),dp(3),dp(4));r.addView(b,p);}
        parent.addView(r);
    }
    private Button key(String label,String code){Button b=button(label,()->submit("press",object("id",selected,"key",code)),code.equals("ok"));b.setContentDescription(code);return b;}
    private Spinner spinner(String[] names){Spinner s=new Spinner(this);ArrayAdapter<String>a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,names);a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);s.setAdapter(a);s.setMinimumHeight(dp(52));controls.add(s);return s;}
    private void buildUi(){
        LinearLayout root=column();root.setBackgroundColor(BG);
        if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
        root.setOnApplyWindowInsetsListener((v,i)->{
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets b=i.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());v.setPadding(b.left,b.top,b.right,b.bottom);}
            else v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;
        });
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);root.addView(scroll);
        LinearLayout content=column();content.setPadding(dp(18),dp(18),dp(18),dp(28));scroll.addView(content);
        content.addView(text("IN3RT1A / ANDROID BETA",12,ORANGE));
        TextView title=text("PC TV Remote",30,Color.WHITE);title.setTypeface(null,Typeface.BOLD);content.addView(title);
        content.addView(text("Your phone. Your TV. No PC needed.",15,MUTED));
        content.addView(text("Use the same Wi-Fi as your TV. VPNs and guest-network isolation can block connections. TV compatibility varies by model.",12,MUTED));
        LinearLayout connect=card(content,"01 / CONNECT A TV");
        brands=spinner(LABELS);brands.setContentDescription("TV brand");connect.addView(brands);
        row(connect,button("Find TVs",()->submit("discover",object("brand",BRANDS[brands.getSelectedItemPosition()])),true),button("Add by IP",this::manualDialog,false));
        televisions=spinner(new String[]{"No saved TVs"});televisions.setContentDescription("Saved TVs");connect.addView(televisions);
        televisions.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            public void onItemSelected(AdapterView<?>p,View v,int n,long id){if(n<saved.size()){selected=saved.get(n).optString("id");getPreferences(MODE_PRIVATE).edit().putString("selected",selected).apply();}}
            public void onNothingSelected(AdapterView<?>p){}
        });
        row(connect,button("Pair / allow",()->submit("pair",object("id",selected)),false),button("Check TV",()->submit("status",object("id",selected)),false),button("Forget",this::forgetDialog,false));
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setIndeterminate(true);progress.setVisibility(View.GONE);connect.addView(progress);
        status=text("Ready. Choose your TV brand.",14,Color.WHITE);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);connect.addView(status);
        LinearLayout remote=card(content,"02 / REMOTE");
        row(remote,key("Power","power"),key("Input","input"),key("Home","home"));
        row(remote,key("Back","back"),key("▲","up"),key("Menu","menu"));
        row(remote,key("◀","left"),key("OK","ok"),key("▶","right"));
        row(remote,key("Info","info"),key("▼","down"),key("Exit","exit"));
        row(remote,key("Vol −","voldown"),key("Mute","mute"),key("Vol +","volup"));
        row(remote,key("CH −","chdown"),key("Search","search"),key("CH +","chup"));
        row(remote,key("Rewind","rev"),key("Play","play"),key("Pause","pause"),key("Forward","fwd"));
        row(remote,key("Replay","replay"),button("Type text",this::textDialog,false));
        remote.addView(text("Buttons vary by model. Power-on requires network standby. Text supports Roku, Samsung and Google TV.",12,MUTED));
        content.addView(text("Pairing keys stay in this app’s private storage. No account or remote server required.",12,MUTED));
        setContentView(root);root.requestApplyInsets();
    }
    private static JSONObject object(String... pairs){JSONObject o=new JSONObject();try{for(int n=0;n<pairs.length;n+=2)o.put(pairs[n],pairs[n+1]);}catch(JSONException e){throw new IllegalArgumentException(e);}return o;}
    private EditText input(String hint,int type){EditText e=new EditText(this);e.setHint(hint);e.setSingleLine(true);e.setInputType(type);e.setPadding(dp(18),dp(10),dp(18),dp(10));return e;}
    private void manualDialog(){String brand=BRANDS[brands.getSelectedItemPosition()];EditText ip=input("192.168.1.20",InputType.TYPE_CLASS_PHONE);
        new AlertDialog.Builder(this).setTitle("Add "+LABELS[brands.getSelectedItemPosition()]).setMessage("Find the TV’s IP address in its network settings.").setView(ip).setNegativeButton("Cancel",null).setPositiveButton("Save TV",(d,w)->submit("add",object("brand",brand,"ip",ip.getText().toString().trim()))).show();}
    private void textDialog(){EditText t=input("Text to type on TV",InputType.TYPE_CLASS_TEXT);new AlertDialog.Builder(this).setTitle("Type on TV").setView(t).setNegativeButton("Cancel",null).setPositiveButton("Send",(d,w)->submit("text",object("id",selected,"text",t.getText().toString()))).show();}
    private void forgetDialog(){if(selected.isEmpty()){status.setText("Select a saved TV first.");return;}new AlertDialog.Builder(this).setTitle("Forget this TV?").setMessage("Its pairing details will be removed from this phone.").setNegativeButton("Cancel",null).setPositiveButton("Forget",(d,w)->submit("forget",object("id",selected))).show();}
    private String wifiIp(){
        wifiNetwork=null;
        ConnectivityManager m=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);if(m==null)return "";
        for(Network n:m.getAllNetworks()){
            NetworkCapabilities c=m.getNetworkCapabilities(n);if(c==null||!c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)||c.hasTransport(NetworkCapabilities.TRANSPORT_VPN))continue;
            LinkProperties p=m.getLinkProperties(n);if(p==null)continue;
            for(LinkAddress a:p.getLinkAddresses())if(a.getAddress() instanceof Inet4Address){wifiNetwork=n;return a.getAddress().getHostAddress();}
        }return "";
    }
    private void setBusy(boolean value){busy=value;for(View v:controls)v.setEnabled(!value);progress.setVisibility(value?View.VISIBLE:View.GONE);}
    private void submit(String operation,JSONObject payload){
        if(busy||destroyed)return;
        if(!operation.equals("list")&&!operation.equals("add")&&!operation.equals("discover")&&selected.isEmpty()){status.setText("Choose or add a saved TV first.");return;}
        String wifi=wifiIp(); final Network network=wifiNetwork;
        if(wifi.isEmpty()&&!operation.equals("list")&&!operation.equals("add")&&!operation.equals("forget")){status.setText("Connect this phone to the same Wi-Fi as the TV, then try again.");return;}
        setBusy(true);status.setText(operation.equals("pair")?"Approve the connection on your TV. Pairing can take up to a minute…":operation.equals("discover")?"Searching this Wi-Fi network. This can take 30 seconds…":"Working…");
        final WeakReference<MainActivity> owner=new WeakReference<>(this);
        final Context app=getApplicationContext();final String directory=getFilesDir().getAbsolutePath();final String request=payload.toString();
        WORKER.execute(()->{
            String response;WifiManager.MulticastLock multicast=null;
            try{
                if(network!=null){ConnectivityManager cm=(ConnectivityManager)app.getSystemService(Context.CONNECTIVITY_SERVICE);if(cm==null||!cm.bindProcessToNetwork(network))throw new IllegalStateException("Wi-Fi disconnected");}
                if(operation.equals("discover")){WifiManager manager=(WifiManager)app.getSystemService(Context.WIFI_SERVICE);if(manager!=null){multicast=manager.createMulticastLock("pctv-discovery");multicast.setReferenceCounted(false);multicast.acquire();}}
                if(!Python.isStarted())Python.start(new AndroidPlatform(app));
                response=Python.getInstance().getModule("remote_bridge").callAttr("call",operation,request,directory,wifi).toString();
            }catch(Exception e){response="{\"ok\":false,\"error\":\"The remote engine could not complete this request. Try again or restart the app.\"}";}
            finally{if(multicast!=null&&multicast.isHeld())multicast.release();}
            final String result=response;
            MAIN.post(()->{MainActivity a=owner.get();if(a==null||a.destroyed||a.isFinishing()||a.isDestroyed())return;a.setBusy(false);a.handle(operation,payload.optString("id"),result);});
        });
    }
    private void showSaved(JSONArray devices){
        saved.clear();List<String> names=new ArrayList<>();int active=0;
        for(int i=0;i<devices.length();i++){JSONObject d=devices.optJSONObject(i);if(d==null)continue;if(selected.equals(d.optString("id")))active=saved.size();saved.add(d);names.add(d.optString("name")+" · "+d.optString("ip"));}
        if(saved.isEmpty()){selected="";names.add("No saved TVs");}else selected=saved.get(active).optString("id");
        ArrayAdapter<String> a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,names);a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);televisions.setAdapter(a);televisions.setSelection(active);
        getPreferences(MODE_PRIVATE).edit().putString("selected",selected).apply();
    }
    private void handle(String operation,String requestedId,String raw){
        try{
            JSONObject r=new JSONObject(raw);if(!r.optBoolean("ok")){status.setText(r.optString("error","Request failed."));return;}
            if(operation.equals("discover")){
                JSONArray found=r.optJSONArray("devices");String warning=r.optString("warning");
                if(found==null||found.length()==0){status.setText(warning.isEmpty()?"No TVs found. Check the brand and Wi-Fi, or use Add by IP.":warning);return;}
                status.setText(warning.isEmpty()?"Found "+found.length()+" TV(s). Choose one to save.":warning);
                String[] labels=new String[found.length()];for(int i=0;i<labels.length;i++){JSONObject d=found.getJSONObject(i);labels[i]=d.optString("name")+" · "+d.optString("ip");}
                new AlertDialog.Builder(this).setTitle("TVs on your Wi-Fi").setItems(labels,(d,w)->{JSONObject tv=found.optJSONObject(w);if(tv!=null)submit("add",tv);}).setNegativeButton("Close",null).show();return;
            }
            if(r.has("device"))selected=r.getJSONObject("device").optString("id",selected);
            if(r.has("devices"))showSaved(r.getJSONArray("devices"));
            if(operation.equals("pair")&&r.optBoolean("pinRequired")){
                status.setText("Enter the pairing code displayed on your TV.");EditText code=input("TV pairing code",InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
                new AlertDialog.Builder(this).setTitle("Enter TV pairing code").setView(code).setNegativeButton("Cancel",null).setPositiveButton("Pair",(d,w)->submit("pair",object("id",requestedId,"pin",code.getText().toString().trim()))).show();
            }else if(operation.equals("pair"))status.setText(r.optBoolean("paired")?"Paired. Your remote is ready.":"Pairing was not completed. Try again.");
            else if(operation.equals("status")){JSONObject s=r.getJSONObject("status");String message=s.optBoolean("online")?"TV is online.":"TV is offline or in standby.";if(s.has("paired")&&!s.optBoolean("paired"))message+=" Pair this TV to send commands.";status.setText(message);}
            else if(operation.equals("add"))status.setText("TV saved. Use Pair / allow if your TV requires pairing.");
            else if(operation.equals("forget"))status.setText("TV forgotten.");
            else if(operation.equals("list"))status.setText(saved.isEmpty()?"Choose your TV brand, then find or add a TV.":"Select your TV, then pair or use the remote.");
            else status.setText("Command sent.");
        }catch(JSONException e){status.setText("Could not read the TV response. Please try again.");}
    }
    @Override protected void onDestroy(){destroyed=true;super.onDestroy();}
}
