#!/usr/bin/env python3
"""Finalise the host-broadcast experiment after host_broadcast_patch.py."""
from pathlib import Path
import sys
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
def edit(path, before, after):
    f=ROOT/path; text=f.read_text("utf-8")
    if before not in text: raise RuntimeError(f"Anchor missing: {path} {before[:100]!r}")
    f.write_text(text.replace(before,after,1),"utf-8")
def write(path,s):
    f=ROOT/path; f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s,"utf-8")
# The in-world televisions are the EXISTING blocks; no new blocks.
edit("src/main/java/com/desktopscreens/client/ScreenRenderer.java",
     "import com.desktopscreens.ScreenBlockEntity;",
     "import com.desktopscreens.ScreenBlockEntity;\nimport com.desktopscreens.HostBroadcast;")
edit("src/main/java/com/desktopscreens/client/ScreenRenderer.java",
     "        if (owner == null) return hintOnly(group, screen, state, hint);",
     """        UUID host = SharingInfo.broadcastHost();
        if (!HostBroadcast.NO_HOST.equals(host)) {
            WorldScreens.Picture stream = host.equals(me)
                ? WorldScreens.picture(mc, SourceChoice.of((UUID)null))
                : SharedPictures.broadcast(mc, host);
            if (stream != null) {
                float[] size = group.pictureRect(stream.cropW(), stream.cropH());
                return new Piece(group, screen.getBlockPos(), state, stream, size, null, false, hint, group.fromGlass(camera));
            }
        }
        if (owner == null) return hintOnly(group, screen, state, hint);""")
# The global virtual stream must be requested by all guests, including those without tablets or physical televisions.
# Audio listener scans it regardless of position. Rendering starts when a tablet/screen is drawn.
# Use render dispatcher-provided matrix: pose may be transformed later by the engine.
edit("src/main/java/com/desktopscreens/client/HeldTablet.java",
     "final Matrix4f m = new Matrix4f(pose.last().pose());\n        collector.submitCustomGeometry(pose, picture.renderType(), (at, out) -> {",
     "collector.submitCustomGeometry(pose, picture.renderType(), (at, out) -> {\n            Matrix4f m = at.pose();")
# Register the server packet. Only the host can change broadcast state; OFF by default.
edit("src/main/java/com/desktopscreens/fabric/DesktopScreensFabric.java",
     "import com.desktopscreens.TabletItem;",
     "import com.desktopscreens.TabletItem;\nimport com.desktopscreens.HostBroadcast;")
edit("src/main/java/com/desktopscreens/fabric/DesktopScreensFabric.java",
     "PayloadTypeRegistry.playC2S().register(ServerCheck.TYPE, ServerCheck.STREAM_CODEC);",
     """PayloadTypeRegistry.playC2S().register(HostBroadcast.Toggle.TYPE, HostBroadcast.Toggle.STREAM_CODEC);
        ServerPlayNetworking.registerGlobalReceiver(HostBroadcast.Toggle.TYPE,
                (payload, context) -> HostBroadcast.toggle(context.player(), payload));
        PayloadTypeRegistry.playC2S().register(ServerCheck.TYPE, ServerCheck.STREAM_CODEC);""")
# The normal button for the settings opens a small French panel rather than capturing the user's PC.
edit("src/main/java/com/desktopscreens/client/DesktopClient.java",
     "public static Screen settingsScreen(Screen parent) {\n        Minecraft mc = Minecraft.getInstance();",
     """public static Screen settingsScreen(Screen parent) {
        return new BroadcastMenu(parent);
    }

    static Screen advancedSettingsScreen(Screen parent) {
        Minecraft mc = Minecraft.getInstance();""")
write("src/main/java/com/desktopscreens/client/BroadcastMenu.java", """package com.desktopscreens.client;
import com.desktopscreens.HostBroadcast;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import java.util.UUID;

/** Minimal French first-party control UI. The advanced source-selection UI is retained. */
public final class BroadcastMenu extends Screen {
    private final Screen back;
    private Button go, audio;
    private boolean locallyEnabled;
    public BroadcastMenu(Screen back) {
        super(Component.literal("Desktop Screens - Diffusion"));
        this.back = back;
    }
    private boolean iAmHost() {
        Minecraft mc=Minecraft.getInstance();
        if (mc.player==null) return false;
        UUID host=SharingInfo.broadcastHost();
        if (HostBroadcast.NO_HOST.equals(host))
            return mc.getSingleplayerServer()!=null
                && mc.player.getUUID().equals(HostBroadcast.owner(mc.getSingleplayerServer()));
        return host.equals(mc.player.getUUID());
    }
    @Override protected void init() {
        DesktopConfig.load();
        int x=width/2-115, y=height/2-48;
        locallyEnabled=!HostBroadcast.NO_HOST.equals(SharingInfo.broadcastHost());
        go=addRenderableWidget(Button.builder(Component.literal("Demarrer le direct"), button -> {
            if (!iAmHost() || minecraft.getConnection()==null) return;
            locallyEnabled=!locallyEnabled;
            ClientNet.toServer(minecraft.getConnection(), new HostBroadcast.Toggle(locallyEnabled));
            button.setMessage(Component.literal(locallyEnabled ? "ARRETER LE DIRECT" : "DEMARRER LE DIRECT"));
        }).bounds(x,y,230,22).build());
        audio=addRenderableWidget(Button.builder(Component.literal("Son du PC"), button -> {
            DesktopConfig.shareSound=!DesktopConfig.shareSound;
            DesktopConfig.save();
            button.setMessage(Component.literal(DesktopConfig.shareSound ? "SON : OUI" : "SON : NON"));
        }).bounds(x,y+27,230,22).build());
        addRenderableWidget(Button.builder(Component.literal("Moniteur / fenetre / options avancees"), button ->
            minecraft.setScreen(DesktopClient.advancedSettingsScreen(this)))
            .bounds(x,y+54,230,22).build());
        addRenderableWidget(Button.builder(Component.literal("Retour"), button -> onClose())
            .bounds(x,y+83,230,22).build());
    }
    @Override public void tick() {
        if (go==null || audio==null) return;
        go.active=iAmHost();
        audio.active=iAmHost();
        go.setMessage(Component.literal(!iAmHost() ? "Seul l'hote peut diffuser" :
                locallyEnabled ? "ARRETER LE DIRECT" : "DEMARRER LE DIRECT"));
        audio.setMessage(Component.literal(DesktopConfig.shareSound ? "SON : OUI" : "SON : NON"));
    }
    @Override public void render(GuiGraphics g,int mouseX,int mouseY,float delta) {
        super.render(g,mouseX,mouseY,delta);
        g.drawCenteredString(font, "DESKTOP SCREENS",width/2,height/2-85,0xFFFFFF);
        g.drawCenteredString(font, "Partage via Essential / Minecraft",width/2,height/2-70,0xA0D8FF);
        g.drawCenteredString(font, "Ecrans existants + tablettes 3D + son global",width/2,height/2+65,0xBBBBBB);
    }
    @Override public void onClose() { minecraft.setScreen(back); }
}
""")
# The broadcast host always sees their desktop on the tablet itself.
# Guests cannot accidentally control the owner's PC, and opening fullscreen remains a separate action.
print("Stage 3 applied")
