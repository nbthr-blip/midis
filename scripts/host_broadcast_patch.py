#!/usr/bin/env python3
"""BOTHIER experimental Essential-host broadcast, global audio and 3D handheld tablet.
Apply to upstream Desktop Screens AFTER desktop_screens_patch.py.
"""
from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

def patch(path, old, new):
    file = ROOT / path
    before = file.read_text(encoding="utf-8")
    if old not in before:
        raise SystemExit(f"Host broadcast patch anchor missing: {path}: {old[:100]}")
    file.write_text(before.replace(old, new, 1), encoding="utf-8")

def write(path, data):
    file = ROOT / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(data, encoding="utf-8")

write("src/main/java/com/desktopscreens/HostBroadcast.java", """package com.desktopscreens;

import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import java.util.UUID;

/**
 * Host-owned optional broadcast in an integrated Minecraft server (Essential/LAN).
 * This is an in-band Minecraft connection; no VPS, sockets, passwords, or paid relay.
 * Only the owner of the singleplayer world is a broadcaster.
 */
public final class HostBroadcast {
    public static final UUID NO_HOST = new UUID(0L, 0L);
    public static final UUID STREAM_ID = new UUID(0L, 2L);
    /** Never an actual world screen: reserved request marker for the in-band stream. */
    public static final BlockPos WATCH_POS = new BlockPos(0, -1000, 0);

    private HostBroadcast() {}

    private static MinecraftServer activeServer;
    private static boolean enabled;

    public static boolean isEnabled(MinecraftServer server) {
        return server != null && server == activeServer && enabled;
    }

    public static void toggle(net.minecraft.server.level.ServerPlayer player, Toggle packet) {
        MinecraftServer server = Players.server(player);
        if (server == null || !player.getUUID().equals(owner(server))) return;
        activeServer = server;
        enabled = packet.enabled();
        for (net.minecraft.server.level.ServerPlayer p : server.getPlayerList().getPlayers())
            ScreenSharing.sendLists(p);
    }

    public record Toggle(boolean enabled) implements net.minecraft.network.protocol.common.custom.CustomPacketPayload {
        public static final Type<Toggle> TYPE = new Type<>(DesktopScreens.id("broadcast_toggle"));
        public static final net.minecraft.network.codec.StreamCodec<io.netty.buffer.ByteBuf, Toggle> STREAM_CODEC =
                net.minecraft.network.codec.StreamCodec.composite(
                        net.minecraft.network.codec.ByteBufCodecs.BOOL, Toggle::enabled, Toggle::new);
        @Override public Type<Toggle> type() { return TYPE; }
    }

    public static UUID owner(MinecraftServer server) {
        if (server == null || server.isDedicatedServer() || server.getSingleplayerProfile() == null) return null;
        return Players.id(server.getSingleplayerProfile());
    }
}
""")

sharing = "src/main/java/com/desktopscreens/ScreenSharing.java"
patch(sharing, "public record Lists(List<UUID> sharingAllWithYou, List<String> yourAllScreens) implements CustomPacketPayload {",
      "public record Lists(List<UUID> sharingAllWithYou, List<String> yourAllScreens, UUID host) implements CustomPacketPayload {")
patch(sharing, "ByteBufCodecs.stringUtf8(ShareScreen.MAX_NAME).apply(ByteBufCodecs.list(MAX_WATCHERS)), Lists::yourAllScreens,\n                Lists::new);",
      "ByteBufCodecs.stringUtf8(ShareScreen.MAX_NAME).apply(ByteBufCodecs.list(MAX_WATCHERS)), Lists::yourAllScreens,\n                Codecs.UUID, Lists::host, Lists::new);")
patch(sharing,
      "return owner != null && (screen.sharedWith(watcher) || SharingData.of(server).sharesAll(owner, watcher));",
      "return owner != null && (owner.equals(HostBroadcast.owner(server)) && HostBroadcast.isEnabled(server) || screen.sharedWith(watcher) || SharingData.of(server).sharesAll(owner, watcher));")
patch(sharing,
      "Net.toPlayer(player, new Lists(data.ownersSharingAllWith(player.getUUID()), names));",
      """UUID host = HostBroadcast.owner(Players.server(player));
        List<UUID> owners = new ArrayList<>(data.ownersSharingAllWith(player.getUUID()));
        if (host != null && HostBroadcast.isEnabled(Players.server(player)) && !host.equals(player.getUUID()) && !owners.contains(host)) owners.add(host);
        Net.toPlayer(player, new Lists(owners, names, host == null || !HostBroadcast.isEnabled(Players.server(player)) ? HostBroadcast.NO_HOST : host));""")

sharing_info = "src/main/java/com/desktopscreens/client/SharingInfo.java"
patch(sharing_info, "import com.desktopscreens.ScreenSharing;", "import com.desktopscreens.ScreenSharing;\nimport com.desktopscreens.HostBroadcast;")
patch(sharing_info, "private static List<String> myAllScreens = List.of();",
      "private static List<String> myAllScreens = List.of();\n    private static UUID broadcastHost = HostBroadcast.NO_HOST;")
patch(sharing_info, "myAllScreens = List.copyOf(lists.yourAllScreens());",
      "myAllScreens = List.copyOf(lists.yourAllScreens());\n        broadcastHost = lists.host();")
patch(sharing_info, "myAllScreens = List.of();\n    }\n\n    /** Whether",
      "myAllScreens = List.of();\n        broadcastHost = HostBroadcast.NO_HOST;\n    }\n\n    static UUID broadcastHost() {\n        return broadcastHost;\n    }\n\n    /** Whether")

relay = "src/main/java/com/desktopscreens/ShareRelay.java"
patch(relay, """        ServerConfig config = ServerConfig.of(Players.server(watcher));
        ServerLevel level = Players.level(watcher);
        BlockPos pos = request.screen();
        if (!config.sharing || !level.isLoaded(pos) || !(level.getBlockEntity(pos) instanceof ScreenBlockEntity screen)) return;""",
"""        ServerConfig config = ServerConfig.of(Players.server(watcher));
        ServerLevel level = Players.level(watcher);
        BlockPos pos = request.screen();
        if (!config.sharing) return;
        // A screen-independent broadcast from the Essential/LAN host: subscribe from ANY distance.
        if (pos.equals(HostBroadcast.WATCH_POS)) {
            UUID host = HostBroadcast.owner(Players.server(watcher));
            if (host == null || host.equals(me) || !HostBroadcast.isEnabled(Players.server(watcher))) return;
            ServerPlayer sender = Players.server(watcher).getPlayerList().getPlayer(host);
            if (sender == null || !ScreenSharing.canReceive.test(sender, ShareStream.Status.TYPE)) return;
            Owner o = OWNERS.computeIfAbsent(host, k -> new Owner());
            Watcher w = o.watchers.computeIfAbsent(me, k -> new Watcher());
            Interest i = w.screens.computeIfAbsent(HostBroadcast.STREAM_ID, k -> new Interest());
            boolean newView = request.pictures() && !i.pictures;
            i.pictures = request.pictures();
            i.sound = request.sound();
            i.pos = HostBroadcast.WATCH_POS;
            i.dimension = level.dimension();
            i.lastSeen = System.currentTimeMillis();
            w.h264 = request.h264();
            tell(sender, o, config);
            if (newView) askKeyframe(sender, o, HostBroadcast.STREAM_ID, i.lastSeen);
            return;
        }
        if (!level.isLoaded(pos) || !(level.getBlockEntity(pos) instanceof ScreenBlockEntity screen)) return;""")
patch(relay,
      "if (player.level().dimension() != i.dimension || player.distanceToSqr(Vec3.atCenterOf(i.pos)) > RANGE * RANGE) return false;",
      """if (i.pos.equals(HostBroadcast.WATCH_POS))
            return owner.equals(HostBroadcast.owner(Players.server(player))) && HostBroadcast.isEnabled(Players.server(player));
        if (player.level().dimension() != i.dimension || player.distanceToSqr(Vec3.atCenterOf(i.pos)) > RANGE * RANGE) return false;""")

# If the host turns on a screen, every player can see it, even without manually adding names.
# In SharingInfo, the host is already in the all-screens list. Virtual stream is only for handheld devices and sound.

pictures="src/main/java/com/desktopscreens/client/SharedPictures.java"
patch(pictures, "import com.desktopscreens.ShareStream;", "import com.desktopscreens.ShareStream;\nimport com.desktopscreens.HostBroadcast;")
patch(pictures, "    /** Marks {@code s} as wanted and puts up its newest picture that's due. */",
"""    /** The Essential host's live desktop for a tablet held by a guest, independent of any placed screens. */
    static WorldScreens.Picture broadcast(Minecraft mc, UUID owner) {
        ShareWatching.Screen screen = new ShareWatching.Screen(owner, HostBroadcast.STREAM_ID);
        ShareWatching.wantPictures(screen, HostBroadcast.WATCH_POS);
        Shown shown = SHOWN.get(screen);
        if (shown == null) return null;
        long now = System.nanoTime();
        Shared current = show(STREAMS.get(shown.current), now);
        if (current == null || current.width == 0) {
            Shared previous = shown.previous != null ? show(STREAMS.get(shown.previous), now) : null;
            if (previous != null && previous.width > 0) current = previous;
        }
        if (current == null || current.width == 0) return null;
        return new WorldScreens.Picture(current.renderType, current.texture, current.width, current.height,
                0, 0, current.width, current.height, null);
    }

    /** Marks {@code s} as wanted and puts up its newest picture that's due. */""")

sound="src/main/java/com/desktopscreens/client/SharedSounds.java"
patch(sound, "import com.desktopscreens.ShareStream;", "import com.desktopscreens.ShareStream;\nimport com.desktopscreens.HostBroadcast;")
patch(sound, """        }
        return nearest;
    }

    private static float volumeAt""",
"""        }
        // Essential's host is audible everywhere, even without a placed screen or any loaded screen chunks.
        UUID host = SharingInfo.broadcastHost();
        if (!HostBroadcast.NO_HOST.equals(host) && !host.equals(me) && connection.getPlayerInfo(host) != null) {
            nearest.put(host, new Near(HostBroadcast.WATCH_POS, HostBroadcast.STREAM_ID, ear, 0));
        }
        return nearest;
    }

    private static float volumeAt""")

# A real 3D tablet, rather than a flat icon. These are ordinary block-model cuboids in 16px model space.
# The north-facing front glass is at z=7; the video plane is 0.016px in front, inside the silver bezel.
write("src/main/resources/assets/desktopscreens/models/item/tablet.json", """{
  "parent": "minecraft:block/block",
  "textures": {
    "case": "minecraft:block/polished_blackstone",
    "edge": "minecraft:block/iron_block",
    "glass": "minecraft:block/black_concrete",
    "accent": "minecraft:block/blue_concrete",
    "particle": "minecraft:block/polished_blackstone"
  },
  "elements": [
    {
      "from": [0.5, 3, 7], "to": [15.5, 13, 9],
      "faces": {
        "north": {"texture":"#edge"}, "south": {"texture":"#case"},
        "east": {"texture":"#case"}, "west": {"texture":"#case"},
        "up": {"texture":"#case"}, "down": {"texture":"#case"}
      }
    },
    {
      "from": [1.1, 3.55, 6.875], "to": [14.9, 12.45, 7],
      "faces": {
        "north": {"texture":"#glass"}, "south": {"texture":"#glass"},
        "up": {"texture":"#edge"}, "down": {"texture":"#edge"},
        "east": {"texture":"#edge"}, "west": {"texture":"#edge"}
      }
    },
    {
      "from": [7.5, 3.12, 6.8125], "to": [8.5, 3.28, 6.875],
      "faces": {"north":{"texture":"#accent"}}
    }
  ]
}
""")

# Draw directly onto the 3D tablet's glass in first-person without opening any full-screen GUI.
write("src/main/java/com/desktopscreens/client/HeldTablet.java", """package com.desktopscreens.client;

import com.desktopscreens.HostBroadcast;
import com.desktopscreens.TabletItem;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import org.joml.Matrix4f;
import java.util.UUID;

/** First-person glass texture, fitted to the real 3D held-tablet model. */
public final class HeldTablet {
    private HeldTablet() {}

    public static void render(LivingEntity owner, ItemStack stack, ItemDisplayContext context,
                              PoseStack pose, SubmitNodeCollector collector) {
        if (!(stack.getItem() instanceof TabletItem)) return;
        if (context != ItemDisplayContext.FIRST_PERSON_RIGHT_HAND && context != ItemDisplayContext.FIRST_PERSON_LEFT_HAND)
            return;
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.level == null || owner != mc.player) return;
        UUID host = SharingInfo.broadcastHost();
        WorldScreens.Picture picture;
        if (!HostBroadcast.NO_HOST.equals(host) && !host.equals(mc.player.getUUID())) {
            picture = SharedPictures.broadcast(mc, host);
        } else {
            // The host sees their own desktop, without waiting for the network to send it back.
            picture = WorldScreens.picture(mc, SourceChoice.of((UUID) null));
        }
        if (picture == null || picture.frameWidth() <= 0 || picture.frameHeight() <= 0) return;

        // Cuboid black glass: model pixels x=1.1..14.9, y=3.55..12.45, front z=6.875.
        // Use a small inset to keep the picture fully within the beveled metal frame.
        float maxW = 12.7f / 16f, maxH = 7.9f / 16f;
        float ratio = picture.cropW() / (float) picture.cropH();
        float w = Math.min(maxW, maxH * ratio), h = w / ratio;
        float x0 = -w / 2f, x1 = w / 2f, y0 = -h / 2f, y1 = h / 2f;
        float z = (6.875f - 8f) / 16f - 0.0025f;
        float u0 = picture.cropX() / (float)picture.frameWidth();
        float u1 = (picture.cropX() + picture.cropW()) / (float)picture.frameWidth();
        float v0 = picture.cropY() / (float)picture.frameHeight();
        float v1 = (picture.cropY() + picture.cropH()) / (float)picture.frameHeight();
        // RenderPipeline is front-face culled. The front of the tablet faces north (-Z).
        final Matrix4f m = new Matrix4f(pose.last().pose());
        collector.submitCustomGeometry(pose, picture.renderType(), (at, out) -> {
            int color = 0xFFFFFFFF;
            Vertices.picture(out, m, x1, y0, z, u1, v1, color);
            Vertices.picture(out, m, x0, y0, z, u0, v1, color);
            Vertices.picture(out, m, x0, y1, z, u0, v0, color);
            Vertices.picture(out, m, x1, y1, z, u1, v0, color);
        });
    }
}
""")

write("src/main/java/com/desktopscreens/mixin/ItemInHandRendererMixin.java", """package com.desktopscreens.mixin;

import com.desktopscreens.client.HeldTablet;
import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.renderer.ItemInHandRenderer;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ItemInHandRenderer.class)
abstract class ItemInHandRendererMixin {
    @Inject(method = "renderItem", at = @At("TAIL"))
    private void desktopscreens$showTablet(LivingEntity owner, ItemStack stack, ItemDisplayContext context,
                                           PoseStack pose, SubmitNodeCollector collector, int light, CallbackInfo ci) {
        HeldTablet.render(owner, stack, context, pose, collector);
    }
}
""")

# Only activate this mixin in the 1.21.11 branch generated by this script.
patch("src/main/resources/desktopscreens.mixins.json",
      '    "KeyboardHandlerMixin",', '    "KeyboardHandlerMixin",\n    "ItemInHandRendererMixin",')

# Don't pop open the local Windows desktop when a guest right-clicks the tablet:
# it already shows the host live in the model, while the host keeps the original control interface.
client="src/main/java/com/desktopscreens/client/DesktopClient.java"
patch(client,
      "TabletItem.onUseClient = () -> tabletPending = true;",
      """TabletItem.onUseClient = () -> {
            Minecraft mc = Minecraft.getInstance();
            UUID host = SharingInfo.broadcastHost();
            if (mc.player == null || HostBroadcast.NO_HOST.equals(host) || host.equals(mc.player.getUUID()))
                tabletPending = true;
            // Guest tablet stays in-hand and displays the host; a right click doesn't hijack their desktop.
        };""")
patch(client, "import com.desktopscreens.ShareStream;", "import com.desktopscreens.ShareStream;\nimport com.desktopscreens.HostBroadcast;\nimport java.util.UUID;")

print("Applied integrated-host auto-sharing, global sound, remote handheld video and 3D tablet.")
