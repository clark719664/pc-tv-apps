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
    private static final int BG=0xff101114, CARD=0xff202227, ORANGE=0xffff9b50, MUTED=0xffa9abb3;
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
    private Button button(String label,Runnable action,boolean accent){
        Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextSize(14);b.setMinWidth(0);b.setMinimumWidth(0);
        b.setPadding(dp(4),dp(5),dp(4),dp(5));b.setTextColor(accent?BG:Color.WHITE);
        b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x44ffffff),surface(accent?ORANGE:0xff34373e),null));
        b.setOnClickListener(v->action.run());controls.add(b);return b;
    }
    private void row(LinearLayout parent,Button... buttons){
        LinearLayout r=new LinearLayout(this);
        for(Button b:buttons){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(56),1);p.setMargins(dp(3),dp(4),dp(3),dp(4));r.addView(b,p);}
        parent.addView(r);
    }
    private Button key(String label,String code){Button b=button(label,()->submit("press",object("id",selected,"key",code)),code.equals("ok"));String description=switch(code){case "volup"->"Volume up";case "voldown"->"Volume down";case "chup"->"Channel up";case "chdown"->"Channel down";case "rev"->"Rewind";case "fwd"->"Fast forward";case "up"->"Up";case "down"->"Down";case "left"->"Left";case "right"->"Right";default->label;};b.setContentDescription(description);return b;}
    private Spinner spinner(String[] names){Spinner s=new Spinner(this);ArrayAdapter<String>a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,names);a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);s.setAdapter(a);s.setMinimumHeight(dp(52));controls.add(s);return s;}
    private void buildUi(){
        LinearLayout root=column();root.setBackgroundColor(BG);
        if(Build.VERSION.SDK_INT>=30)getWindow().setDecorFitsSystemWindows(false);
        root.setOnApplyWindowInsetsListener((v,i)->{
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets b=i.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout()|WindowInsets.Type.ime());v.setPadding(b.left,b.top,b.right,b.bottom);}
            else v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;
        });
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);root.addView(scroll);
        LinearLayout content=column();content.setGravity(Gravity.CENTER_HORIZONTAL);content.setPadding(dp(12),dp(10),dp(12),dp(24));scroll.addView(content);
        int width=Math.min(dp(364),getResources().getDisplayMetrics().widthPixels-dp(24));
        LinearLayout header=column();content.addView(header,new LinearLayout.LayoutParams(width,-2));
        LinearLayout heading=new LinearLayout(this);heading.setGravity(Gravity.CENTER_VERTICAL);header.addView(heading);
        TextView title=text("PC TV Remote",20,Color.WHITE);title.setTypeface(null,Typeface.BOLD);heading.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        heading.addView(button("TVs",this::manageDialog,false),new LinearLayout.LayoutParams(dp(64),dp(48)));
        televisions=spinner(new String[]{"No saved TVs"});televisions.setContentDescription("Saved TVs");header.addView(televisions);
        televisions.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            public void onItemSelected(AdapterView<?>p,View v,int n,long id){if(n<saved.size()){selected=saved.get(n).optString("id");getPreferences(MODE_PRIVATE).edit().putString("selected",selected).apply();}}
            public void onNothingSelected(AdapterView<?>p){}
        });
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setIndeterminate(true);progress.setVisibility(View.INVISIBLE);header.addView(progress,new LinearLayout.LayoutParams(-1,dp(3)));
        status=text("Choose a TV to get started.",12,MUTED);status.setMinHeight(dp(40));status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);header.addView(status);
        LinearLayout remote=column();remote.setGravity(Gravity.CENTER_HORIZONTAL);remote.setPadding(dp(16),dp(16),dp(16),dp(18));
        GradientDrawable shell=surface(CARD);shell.setCornerRadius(dp(38));shell.setStroke(dp(1),0xff42454c);remote.setBackground(shell);remote.setElevation(dp(6));
        content.addView(remote,new LinearLayout.LayoutParams(width,-2));
        LinearLayout top=new LinearLayout(this);top.setGravity(Gravity.CENTER_VERTICAL);remote.addView(top,new LinearLayout.LayoutParams(-1,-2));
        Button power=key("","power");power.setForeground(getDrawable(R.drawable.ic_power));power.setForegroundGravity(Gravity.CENTER);power.setContentDescription("Power");top.addView(power,new LinearLayout.LayoutParams(dp(58),dp(52)));
        TextView mark=text("IN3RT1A",12,MUTED);mark.setGravity(Gravity.CENTER);mark.setLetterSpacing(.18f);top.addView(mark,new LinearLayout.LayoutParams(0,-2,1));
        Button source=button("Input",this::inputAction,false);source.setContentDescription("Input");top.addView(source,new LinearLayout.LayoutParams(dp(64),dp(52)));
        row(remote,key("Back","back"),key("Home","home"),key("Menu","menu"));
        FrameLayout pad=new FrameLayout(this);GradientDrawable ring=surface(0xff30333a);ring.setCornerRadius(dp(112));ring.setStroke(dp(1),0xff4d5058);pad.setBackground(ring);
        LinearLayout.LayoutParams padParams=new LinearLayout.LayoutParams(dp(224),dp(224));padParams.setMargins(0,dp(12),0,dp(12));remote.addView(pad,padParams);
        direction(pad,"▲","up",Gravity.TOP|Gravity.CENTER_HORIZONTAL,76,64);
        direction(pad,"▼","down",Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL,76,64);
        direction(pad,"◀","left",Gravity.LEFT|Gravity.CENTER_VERTICAL,64,76);
        direction(pad,"▶","right",Gravity.RIGHT|Gravity.CENTER_VERTICAL,64,76);
        Button ok=key("OK","ok");ok.setTextSize(22);ok.setTypeface(null,Typeface.BOLD);GradientDrawable center=surface(ORANGE);center.setCornerRadius(dp(40));
        ok.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x55ffffff),center,null));pad.addView(ok,new FrameLayout.LayoutParams(dp(80),dp(80),Gravity.CENTER));
        LinearLayout rockers=new LinearLayout(this);rockers.setGravity(Gravity.CENTER_VERTICAL);remote.addView(rockers,new LinearLayout.LayoutParams(-1,-2));
        rocker(rockers,"VOLUME","volup","voldown");
        LinearLayout middle=column();middle.setGravity(Gravity.CENTER);LinearLayout.LayoutParams mid=new LinearLayout.LayoutParams(0,-2,1);mid.setMargins(dp(10),0,dp(10),0);rockers.addView(middle,mid);
        middle.addView(key("Mute","mute"),new LinearLayout.LayoutParams(-1,dp(52)));TextView live=text("WI-FI\nREMOTE",10,MUTED);live.setGravity(Gravity.CENTER);middle.addView(live);
        rocker(rockers,"CHANNEL","chup","chdown");
        View divider=new View(this);divider.setBackgroundColor(0xff41434a);LinearLayout.LayoutParams line=new LinearLayout.LayoutParams(-1,dp(1));line.setMargins(dp(4),dp(15),dp(4),dp(10));remote.addView(divider,line);
        Button play=key("▶","play"),pause=key("II","pause");play.setContentDescription("Play");pause.setContentDescription("Pause");
        row(remote,key("≪","rev"),play,pause,key("≫","fwd"));
        Button typing=button("Text",this::textDialog,false);typing.setContentDescription("Type text on TV");
        row(remote,key("Replay","replay"),typing,button("More",this::moreDialog,false));
        TextView footer=text("DIRECT TO TV · NO PC NEEDED",10,MUTED);footer.setGravity(Gravity.CENTER);footer.setPadding(0,dp(18),0,0);content.addView(footer);
        setContentView(root);root.requestApplyInsets();
    }
    private void direction(FrameLayout pad,String label,String code,int gravity,int width,int height){
        Button b=key(label,code);b.setTextSize(22);GradientDrawable clear=surface(Color.TRANSPARENT);clear.setCornerRadius(dp(32));
        b.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x44ffffff),clear,null));
        pad.addView(b,new FrameLayout.LayoutParams(dp(width),dp(height),gravity));
    }
    private void rocker(LinearLayout parent,String label,String up,String down){
        LinearLayout r=column();r.setGravity(Gravity.CENTER);r.setPadding(dp(4),dp(4),dp(4),dp(4));r.setBackground(surface(0xff15171b));parent.addView(r,new LinearLayout.LayoutParams(0,-2,1));
        Button plus=key("+",up),minus=key("−",down);plus.setTextSize(24);minus.setTextSize(24);
        r.addView(plus,new LinearLayout.LayoutParams(-1,dp(48)));TextView caption=text(label,10,MUTED);caption.setGravity(Gravity.CENTER);r.addView(caption);r.addView(minus,new LinearLayout.LayoutParams(-1,dp(48)));
    }
    private void manageDialog(){
        int first=controls.size();LinearLayout panel=column();panel.setPadding(dp(18),dp(8),dp(18),dp(8));
        panel.addView(text("Keep your phone and TV on the same Wi-Fi.",14,MUTED));brands=spinner(LABELS);brands.setContentDescription("TV brand");panel.addView(brands);
        for(JSONObject tv:saved)if(selected.equals(tv.optString("id")))for(int i=0;i<BRANDS.length;i++)if(BRANDS[i].equals(tv.optString("brand")))brands.setSelection(i);
        ScrollView scroll=new ScrollView(this);scroll.addView(panel);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Your TVs").setView(scroll).setNegativeButton("Close",null).create();
        row(panel,button("Find TVs",()->{String brand=BRANDS[brands.getSelectedItemPosition()];dialog.dismiss();submit("discover",object("brand",brand));},true),button("Add by IP",()->{dialog.dismiss();manualDialog();},false));
        row(panel,button("Pair / allow",()->{dialog.dismiss();submit("pair",object("id",selected));},false),button("Check TV",()->{dialog.dismiss();submit("status",object("id",selected));},false));
        row(panel,button("Forget TV",()->{dialog.dismiss();forgetDialog();},false));
        panel.addView(text("Pairing keys stay on this phone. Some buttons depend on your TV model; power-on needs network standby.",12,MUTED));
        dialog.setOnDismissListener(d->controls.subList(first,controls.size()).clear());dialog.show();
    }
    private void moreDialog(){String[] labels={"Info","Search","Exit"},keys={"info","search","exit"};new AlertDialog.Builder(this).setTitle("More controls").setItems(labels,(d,w)->submit("press",object("id",selected,"key",keys[w]))).setNegativeButton("Close",null).show();}
    private void inputAction(){
        for(JSONObject tv:saved)if(selected.equals(tv.optString("id"))&&tv.optString("brand").equals("roku")){submit("inputs",object("id",selected));return;}
        submit("press",object("id",selected,"key","input"));
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
    private void setBusy(boolean value){busy=value;for(View v:controls)v.setEnabled(!value);progress.setVisibility(value?View.VISIBLE:View.INVISIBLE);}
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
            if(operation.equals("inputs")){
                JSONArray inputs=r.getJSONArray("inputs");String[] labels=new String[inputs.length()];for(int i=0;i<labels.length;i++){JSONObject entry=inputs.getJSONObject(i);String id=entry.optString("id");String port=id.startsWith("tvinput.hdmi")?"HDMI "+id.substring(12):id.equals("tvinput.dtv")?"Antenna":id.equals("tvinput.cvbs")?"AV":"";labels[i]=entry.optString("name")+(port.isEmpty()?"":" · "+port);}
                status.setText("Choose the input to watch.");new AlertDialog.Builder(this).setTitle("TV inputs").setItems(labels,(d,w)->{JSONObject entry=inputs.optJSONObject(w);if(entry!=null)submit("input",object("id",requestedId,"input",entry.optString("id")));}).setNegativeButton("Cancel",null).show();return;
            }
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
            else if(operation.equals("list"))status.setText(saved.isEmpty()?"Tap TVs to find or add your TV.":"Ready when you are.");
            else status.setText("Command sent.");
        }catch(JSONException e){status.setText("Could not read the TV response. Please try again.");}
    }
    @Override protected void onDestroy(){destroyed=true;super.onDestroy();}
}
