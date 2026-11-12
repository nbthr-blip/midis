#!/usr/bin/env python3
"""V4 handheld tablet renderer and GUI; applied after v4_patch.py."""
from pathlib import Path
import json,sys
R=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()
def put(path,src):
 p=R/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src,encoding="utf-8")
def rep(path,a,b):
 p=R/path;s=p.read_text("utf-8")
 if a not in s:raise SystemExit("Missing V4 anchor "+path+": "+a[:100])
 p.write_text(s.replace(a,b,1),"utf-8")

put("src/main/java/com/desktopscreens/client/TabletChannels.java", """package com.desktopscreens.client;
import com.desktopscreens.HostBroadcast;
import com.desktopscreens.ScreenBlockEntity;
import com.desktopscreens.TabletItem;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import java.util.*;
final class TabletChannels {
    record Channel(UUID owner,UUID id,BlockPos pos,String label) {}
    private static UUID selectedId,selectedOwner;
    private TabletChannels(){}
    static UUID host(Minecraft mc) {
        UUID id=SharingInfo.broadcastHost();
        if(!HostBroadcast.NO_HOST.equals(id))return id;
        if(mc.player!=null && mc.getSingleplayerServer()!=null)return HostBroadcast.owner(mc.getSingleplayerServer());
        return HostBroadcast.NO_HOST;
    }
    static List<Channel> list(Minecraft mc) {
        if(mc.player==null || mc.level==null)return List.of();
        UUID host=host(mc);
        if(HostBroadcast.NO_HOST.equals(host))return List.of();
        Set<UUID> seen=new HashSet<>();
        List<Channel> choices=new ArrayList<>();
        for(ScreenBlockEntity block:ScreenBlockEntity.clientLoaded()) {
            if(block.isRemoved() || block.getLevel()!=mc.level || !host.equals(block.owner()))continue;
            UUID id=block.screenId();
            if(id==null || !seen.add(id))continue;
            BlockPos pos=block.getBlockPos();
            choices.add(new Channel(host,id,pos.immutable(),
                "Ecran "+pos.getX()+", "+pos.getY()+", "+pos.getZ()));
        }
        choices.sort(Comparator.comparing(Channel::label));
        choices.add(new Channel(host,HostBroadcast.STREAM_ID,HostBroadcast.WATCH_POS,"Bureau de l'hote"));
        return choices;
    }
    static Channel selected(Minecraft mc) {
        List<Channel> options=list(mc);
        if(options.isEmpty())return null;
        UUID owner=options.get(0).owner();
        if(!owner.equals(selectedOwner)){selectedOwner=owner;selectedId=null;}
        if(selectedId!=null)for(Channel c:options)if(c.id().equals(selectedId))return c;
        return options.get(0);
    }
    static void select(Channel c){selectedOwner=c.owner();selectedId=c.id();}
    static Channel held(Minecraft mc){
        if(mc.player==null)return null;
        if(!(mc.player.getMainHandItem().getItem() instanceof TabletItem)
            && !(mc.player.getOffhandItem().getItem() instanceof TabletItem))return null;
        return selected(mc);
    }
    static WorldScreens.Picture picture(Minecraft mc) {
        Channel c=selected(mc);
        if(c==null || mc.player==null)return null;
        if(c.owner().equals(mc.player.getUUID())){
            UUID screen=c.id().equals(HostBroadcast.STREAM_ID)?null:c.id();
            return WorldScreens.picture(mc,SourceChoice.of(screen));
        }
        if(c.id().equals(HostBroadcast.STREAM_ID))return SharedPictures.broadcast(mc,c.owner());
        return SharedPictures.channel(mc,c.owner(),c.id(),c.pos());
    }
}
""")

put("src/main/java/com/desktopscreens/client/Theme.java","""package com.desktopscreens.client;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.network.chat.Component;
final class Theme {
    static final int CREAM=0xFFF3E8D8,PLUM=0xFF68438E,INK=0xFF30223B;
    private Theme(){}
    static void panel(GuiGraphics g,int w,int h,String title,String subtitle) {
        int x=w/2-165,y=h/2-120;
        g.fill(0,0,w,h,0xD8161220);
        g.fill(x-3,y-3,x+333,y+243,0xBB9D81BF);
        g.fillGradient(x,y,x+330,y+240,CREAM,0xFFE6D5C6);
        g.fillGradient(x,y,x+330,y+56,PLUM,0xFF8E69AF);
        int shimmer=(int)(Math.sin(System.nanoTime()/400000000.0)*18);
        g.fill(x+80+shimmer,y+54,x+128+shimmer,y+56,0xFFD8C1EF);
        g.drawCenteredString(Minecraft.getInstance().font,title,w/2,y+13,0xFFFFFFFF);
        g.drawCenteredString(Minecraft.getInstance().font,subtitle,w/2,y+34,0xFFF4EAFB);
    }
    static Button button(int x,int y,int w,int h,String label,Button.OnPress click){
        return new Styled(x,y,w,h,Component.literal(label),click);
    }
    private static final class Styled extends Button {
        Styled(int x,int y,int w,int h,Component label,OnPress action) {
            super(x,y,w,h,label,action,DEFAULT_NARRATION);
        }
        @Override protected void renderContents(GuiGraphics g,int mouseX,int mouseY,float delta) {
            boolean hover=isHoveredOrFocused() && active;
            g.fillGradient(getX(),getY(),getX()+getWidth(),getY()+getHeight(),
                !active?0xFFAEA1BA:hover?0xFF9E76C6:0xFF68438E,
                !active?0xFF91869D:hover?0xFF7E56AA:0xFF503270);
            g.drawCenteredString(Minecraft.getInstance().font,getMessage(),
                getX()+getWidth()/2,getY()+getHeight()/2-4,0xFFFFFFFF);
        }
    }
}
""")

put("src/main/java/com/desktopscreens/client/TabletChannelMenu.java","""package com.desktopscreens.client;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import java.util.List;
final class TabletChannelMenu extends Screen {
    private final Screen back;
    private int page=0;
    TabletChannelMenu(Screen back) {super(Component.literal("Tablette - Directs"));this.back=back;}
    @Override protected void init() {
        List<TabletChannels.Channel> list=TabletChannels.list(minecraft);
        int left=width/2-127,top=height/2-54;
        for(int i=0;i<4 && page*4+i<list.size();i++){
            TabletChannels.Channel c=list.get(page*4+i);
            addRenderableWidget(Theme.button(left,top+i*28,254,23,c.label(),b->{
                TabletChannels.select(c);
                onClose();
            }));
        }
        if(page>0)addRenderableWidget(Theme.button(left,top+121,97,21,"< PRECEDENT",b->{page--;rebuildWidgets();}));
        if((page+1)*4<list.size())
            addRenderableWidget(Theme.button(left+157,top+121,97,21,"SUIVANT >",b->{page++;rebuildWidgets();}));
        addRenderableWidget(Theme.button(left+75,top+149,104,21,"RETOUR",b->onClose()));
    }
    @Override public void renderBackground(GuiGraphics g,int mx,int my,float delta){
        Theme.panel(g,width,height,"TABLETTE / DIRECTS","Choisis l'ecran que tu veux regarder");
    }
    @Override public void render(GuiGraphics g,int mx,int my,float delta) {
        super.render(g,mx,my,delta);
        g.drawCenteredString(font,"Seul l'hote controle les fenetres",width/2,height/2+98,Theme.INK);
    }
    @Override public void onClose(){minecraft.setScreen(back);}
}
""")

put("src/main/java/com/desktopscreens/client/HeldTablet.java","""package com.desktopscreens.client;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.SubmitNodeCollector;
import org.joml.Matrix4f;
public final class HeldTablet {
    private HeldTablet(){}
    public static void renderModel(PoseStack pose,SubmitNodeCollector collector) {
        Minecraft mc=Minecraft.getInstance();
        if(mc.player==null || mc.level==null)return;
        WorldScreens.Picture picture=TabletChannels.picture(mc);
        if(picture==null || picture.frameWidth()<=0 || picture.frameHeight()<=0 || picture.cropH()<=0)return;
        float ratio=picture.cropW()/(float)picture.cropH();
        float width=Math.min(12.7F/16F,7.9F/16F*ratio);
        float height=width/ratio;
        float x0=-width/2,x1=width/2,y0=-height/2,y1=height/2;
        float z=(6.875F-8F)/16F-0.0025F;
        float u0=picture.cropX()/(float)picture.frameWidth();
        float u1=(picture.cropX()+picture.cropW())/(float)picture.frameWidth();
        float v0=picture.cropY()/(float)picture.frameHeight();
        float v1=(picture.cropY()+picture.cropH())/(float)picture.frameHeight();
        collector.submitCustomGeometry(pose,picture.renderType(),(at,out)->{
            Matrix4f m=at.pose();
            Vertices.picture(out,m,x1,y0,z,u1,v1,0xFFFFFFFF);
            Vertices.picture(out,m,x0,y0,z,u0,v1,0xFFFFFFFF);
            Vertices.picture(out,m,x0,y1,z,u0,v0,0xFFFFFFFF);
            Vertices.picture(out,m,x1,y1,z,u1,v0,0xFFFFFFFF);
        });
    }
}
""")

put("src/main/java/com/desktopscreens/mixin/ItemInHandRendererMixin.java","""package com.desktopscreens.mixin;
import com.desktopscreens.TabletItem;
import com.desktopscreens.client.HeldTablet;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.ItemInHandRenderer;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.core.component.DataComponentType;
import net.minecraft.core.component.DataComponents;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ItemInHandRenderer.class)
abstract class ItemInHandRendererMixin {
    @Shadow public abstract void renderItem(LivingEntity owner,ItemStack stack,ItemDisplayContext context,
                                            PoseStack pose,SubmitNodeCollector collector,int light);
    @Redirect(method="renderArmWithItem",at=@At(value="INVOKE",
        target="Lnet/minecraft/world/item/ItemStack;has(Lnet/minecraft/core/component/DataComponentType;)Z"))
    private boolean desktopscreens$tabletPose(ItemStack stack,DataComponentType<?> component) {
        if(component==DataComponents.MAP_ID && stack.getItem() instanceof TabletItem)return true;
        return stack.has(component);
    }
    @Inject(method="renderMap",at=@At("HEAD"),cancellable=true)
    private void desktopscreens$renderMapTablet(PoseStack pose,SubmitNodeCollector collector,int light,
                                               ItemStack stack,CallbackInfo ci) {
        if(!(stack.getItem() instanceof TabletItem))return;
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(180.0F));
        pose.mulPose(Axis.ZP.rotationDegrees(180.0F));
        pose.scale(0.62F,0.62F,0.62F);
        this.renderItem(Minecraft.getInstance().player,stack,ItemDisplayContext.FIXED,pose,collector,light);
        HeldTablet.renderModel(pose,collector);
        pose.popPose();
        ci.cancel();
    }
}
""")

p="src/main/java/com/desktopscreens/client/DesktopClient.java"
rep(p, """TabletItem.onUseClient = () -> {
            Minecraft mc = Minecraft.getInstance();
            UUID host = SharingInfo.broadcastHost();
            if (mc.player == null || HostBroadcast.NO_HOST.equals(host) || host.equals(mc.player.getUUID()))
                tabletPending = true;
            // Guest tablet stays in-hand and displays the host; a right click doesn't hijack their desktop.
        };""",
"""TabletItem.onUseClient = () -> {
            Minecraft mc=Minecraft.getInstance();
            if(mc.level!=null && mc.screen==null)mc.setScreen(new TabletChannelMenu(null));
        };""")
rep(p,"else if (tablet && hasTablet(mc)) openDesktop(mc);",
      "else if (tablet && hasTablet(mc)) mc.setScreen(new TabletChannelMenu(null));")

put("src/main/java/com/desktopscreens/client/BroadcastMenu.java","""package com.desktopscreens.client;
import com.desktopscreens.HostBroadcast;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import java.util.UUID;
public final class BroadcastMenu extends Screen {
    private final Screen back;
    private Button go,audio;
    private boolean running;
    public BroadcastMenu(Screen back) {super(Component.literal("Desktop Screens / Direct"));this.back=back;}
    private boolean iAmHost() {
        Minecraft mc=Minecraft.getInstance();
        return mc.player!=null && mc.getSingleplayerServer()!=null
            && mc.player.getUUID().equals(HostBroadcast.owner(mc.getSingleplayerServer()));
    }
    @Override protected void init() {
        DesktopConfig.load();
        int x=width/2-125,y=height/2-55;
        running=!HostBroadcast.NO_HOST.equals(SharingInfo.broadcastHost());
        go=addRenderableWidget(Theme.button(x,y,250,24,"DEMARRER LE DIRECT",b->{
            if(!iAmHost() || minecraft.getConnection()==null)return;
            running=!running;
            ClientNet.toServer(minecraft.getConnection(),new HostBroadcast.Toggle(running));
            b.setMessage(Component.literal(running?"ARRETER LE DIRECT":"DEMARRER LE DIRECT"));
        }));
        audio=addRenderableWidget(Theme.button(x,y+30,250,24,"SON : OUI",b->{
            DesktopConfig.shareSound=!DesktopConfig.shareSound;DesktopConfig.save();
            b.setMessage(Component.literal(DesktopConfig.shareSound?"SON : OUI":"SON : NON"));
        }));
        addRenderableWidget(Theme.button(x,y+60,250,24,"CHOISIR FENETRE / MONITEUR",b->
            minecraft.setScreen(DesktopClient.advancedSettingsScreen(this))));
        addRenderableWidget(Theme.button(x,y+92,250,22,"RETOUR",b->onClose()));
    }
    @Override public void tick() {
        if(go==null || audio==null)return;
        go.active=iAmHost();audio.active=iAmHost();
        go.setMessage(Component.literal(!iAmHost()?"SEUL L'HOTE PEUT DIFFUSER":
            running?"ARRETER LE DIRECT":"DEMARRER LE DIRECT"));
        audio.setMessage(Component.literal(DesktopConfig.shareSound?"SON : OUI":"SON : NON"));
    }
    @Override public void renderBackground(GuiGraphics g,int mx,int my,float delta) {
        Theme.panel(g,width,height,"DESKTOP SCREENS","Partage Minecraft / Essential");
    }
    @Override public void render(GuiGraphics g,int mx,int my,float delta) {
        super.render(g,mx,my,delta);
        g.drawCenteredString(font,"Chaque ecran peut montrer une autre fenetre",width/2,height/2+72,Theme.INK);
        g.drawCenteredString(font,"G sur un ecran, puis Ctrl droit + W",width/2,height/2+86,Theme.INK);
        g.drawCenteredString(font,"Tablette : clic droit pour choisir",width/2,height/2+100,Theme.PLUM);
    }
    @Override public void onClose(){minecraft.setScreen(back);}
}
""")

p="src/main/resources/assets/desktopscreens/models/item/tablet.json"
model=json.loads((R/p).read_text("utf-8"))
model["display"]={
"firstperson_righthand":{"rotation":[0,0,0],"translation":[0,0,0],"scale":[1,1,1]},
"firstperson_lefthand":{"rotation":[0,0,0],"translation":[0,0,0],"scale":[1,1,1]},
"gui":{"rotation":[15,0,0],"translation":[0,0,0],"scale":[0.85,0.85,0.85]},
"ground":{"rotation":[0,0,0],"translation":[0,2,0],"scale":[0.45,0.45,0.45]},
"fixed":{"rotation":[0,0,0],"translation":[0,0,0],"scale":[1,1,1]}
}
put(p,json.dumps(model,ensure_ascii=False,indent=2)+"\n")
print("V4 patch stage 2: tablet channel selector, responsive map pose and simplified themed menus.")
