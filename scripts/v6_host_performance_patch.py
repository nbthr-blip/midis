#!/usr/bin/env python3
"""Desktop Screens V6 - prioritise integrated-server host performance.

Opt-in visual streaming remains unchanged. Performance controls are local
and never transmit private window names, profiles, or configuration.
Run AFTER V5 patches.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

def edit(path, old, new):
    target = root / path
    data = target.read_text(encoding="utf-8")
    if old not in data:
        raise SystemExit("V6 patch anchor missing: %s :: %s" % (path, old[:120]))
    target.write_text(data.replace(old, new, 1), encoding="utf-8")

def create(path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8")

client = "src/main/java/com/desktopscreens/client/"

create(client + "HostPerformance.java", """package com.desktopscreens.client;

import net.minecraft.client.Minecraft;

/**
 * Automatically protects the singleplayer host's Minecraft frame rate:
 * caps Windows capture, GPU texture uploads and background video encoding.
 * The host may switch preset in the settings menu.
 * Never throttles guests or dedicated servers.
 */
final class HostPerformance {
    private static final long SAMPLE_PERIOD = 5_000_000_000L;
    private static volatile int loadLevel; // 0=healthy, 1=slow, 2=very slow
    private static long nextSample;
    private HostPerformance() {}

    static boolean active(Minecraft mc) {
        return mc != null && mc.getSingleplayerServer() != null;
    }

    static void tick(Minecraft mc) {
        if (!active(mc)) {
            loadLevel = 0;
            nextSample = 0;
            return;
        }
        long now = System.nanoTime();
        if (now < nextSample) return;
        nextSample = now + SAMPLE_PERIOD;
        int fps = mc.getFps();
        if (fps <= 0) return;
        // Strong hysteresis on recovery so H.264 does not recreate its encoder
        // every time a frame-rate fluctuates near a threshold.
        int old = loadLevel;
        if (fps < 28) loadLevel = 2;
        else if (fps < 46) loadLevel = Math.max(1, old);
        else if (fps >= 78) loadLevel = 0;
        else if (fps >= 58 && old == 2) loadLevel = 1;
        else if (fps >= 58 && old == 1) loadLevel = 0;
    }

    private static int profile() {
        DesktopConfig.load();
        return DesktopConfig.performanceProfile;
    }

    static String profileName() {
        return switch (profile()) {
            case 1 -> "EQUILIBRE";
            case 2 -> "QUALITE";
            default -> "TURBO (FPS)";
        };
    }

    static int captureFps(Minecraft mc) {
        if (!active(mc)) return 60;
        int base = switch (profile()) {
            case 1 -> 26;
            case 2 -> 36;
            default -> 18;
        };
        if (loadLevel == 2) return Math.min(base, 10);
        if (loadLevel == 1) return Math.min(base, 14);
        return base;
    }

    static long uploadIntervalNs(Minecraft mc) {
        if (!active(mc)) return 0L;
        return 1_000_000_000L / Math.max(1, captureFps(mc));
    }

    static int sharedFps(Minecraft mc, int streams) {
        if (!active(mc)) return 60;
        int base = switch (profile()) {
            case 1 -> 22;
            case 2 -> 30;
            default -> 16;
        };
        if (loadLevel == 2) base = Math.min(base, 7);
        else if (loadLevel == 1) base = Math.min(base, 11);
        // Three or four DISTINCT Windows must not saturate the game CPU.
        int total = streams <= 2 ? base : Math.min(base, Math.max(7, 36 / streams));
        return Math.max(5, total);
    }

    static int sharedMaxWidth(Minecraft mc) {
        if (!active(mc)) return 1920;
        if (loadLevel == 2) return 640;
        if (loadLevel == 1) return 800;
        return switch (profile()) {
            case 1 -> 1100;
            case 2 -> 1600;
            default -> 960;
        };
    }

    static int sharedMaxHeight(Minecraft mc) {
        if (!active(mc)) return 1080;
        if (loadLevel == 2) return 360;
        if (loadLevel == 1) return 450;
        return switch (profile()) {
            case 1 -> 620;
            case 2 -> 900;
            default -> 540;
        };
    }

    static boolean quickResize(Minecraft mc) {
        return active(mc) && profile() == 0;
    }

    static String diagnostic(Minecraft mc) {
        return "Profil : " + profileName() + "   |   Minecraft : " + mc.getFps()
                + " FPS   |   Video : " + sharedFps(mc, 1) + " FPS"
                + (loadLevel > 0 ? "   |   Reduction automatique active" : "");
    }
}
""")

# Local-only settings: controls *video capture* and *encoding* on the integrated host.
# Existing server limits remain upper bounds and have never been overridden.
settings = client + "DesktopConfig.java"
edit(settings,
     "    static boolean shareSound = true;",
     "    static boolean shareSound = true;\n    /** 0: performance/Turbo, 1: balanced, 2: quality. Host only. */\n    static int performanceProfile = 0;")
edit(settings,
     '        shareSound = Boolean.parseBoolean(p.getProperty("sharing.sound", Boolean.toString(shareSound)).trim());',
     '        shareSound = Boolean.parseBoolean(p.getProperty("sharing.sound", Boolean.toString(shareSound)).trim());\n        performanceProfile = intValue(p, "performance.profile", performanceProfile, 0, 2);')
edit(settings,
     '        p.setProperty("sharing.sound", Boolean.toString(shareSound));',
     '        p.setProperty("sharing.sound", Boolean.toString(shareSound));\n        p.setProperty("performance.profile", Integer.toString(performanceProfile));')

# Original 30fps, 1280x720, four encoder workers PER WINDOW made host performance plummet.
# Reduce encode threads, JPEG work and prioritize Minecraft's render/integrated-server threads.
streamer = client + "ShareStreamer.java"
edit(streamer, "private static final int QUALITY = 80, STRIPS = 4;",
              "private static final int QUALITY = 66, STRIPS = 2;")
edit(streamer, "    static void tick(Minecraft mc) {\n        if (mc.level == null) {",
              "    static void tick(Minecraft mc) {\n        HostPerformance.tick(mc);\n        if (mc.level == null) {")
edit(streamer, "            t.setDaemon(true);\n            return t;\n        });",
              "            t.setDaemon(true);\n            t.setPriority(Math.max(Thread.MIN_PRIORITY, Thread.NORM_PRIORITY - 1));\n            return t;\n        });")
edit(streamer,
     '            Thread thread = new Thread(this, "Desktop Screens sharing, stream " + stream);\n            thread.setDaemon(true);\n            thread.start();',
     '            Thread thread = new Thread(this, "Desktop Screens sharing, stream " + stream);\n            thread.setDaemon(true);\n            thread.setPriority(Math.max(Thread.MIN_PRIORITY, Thread.NORM_PRIORITY - 1));\n            thread.start();')
edit(streamer,
     """            fps = Math.max(1, limits.maxFps());
            maxW = limits.maxWidth();
            maxH = limits.maxHeight();""",
     """            fps = Math.max(1, Math.min(limits.maxFps(), HostPerformance.sharedFps(mc, SENDERS.size())));
            maxW = Math.min(limits.maxWidth(), HostPerformance.sharedMaxWidth(mc));
            maxH = Math.min(limits.maxHeight(), HostPerformance.sharedMaxHeight(mc));""")
edit(streamer, "                    copy.source = c;\n                    copy.crop = crop;",
              """                    copy.source = c;
                    copy.crop = crop;
                    copy.limitW = maxW;
                    copy.limitH = maxH;
                    copy.quickResize = HostPerformance.quickResize(mc);""")
edit(streamer, "                        Thread.sleep(2);\n                        continue;",
              "                        Thread.sleep(6);\n                        continue;")
edit(streamer, "                        Thread.sleep(4);\n                        continue;",
              "                        Thread.sleep(8);\n                        continue;")

# Avoid copying/rehashing 3840x2160 at 16 fps AND then bilinear-scaling it.
# In Turbo the one capture read directly creates the small frame: 500k
# output pixels rather than copying/hashing 8 million raw pixels first.
edit(streamer, """        int[] crop;
        long buffer, capacity, taken;
        int width, height;""",
"""        int[] crop;
        long buffer, capacity, taken;
        int width, height;
        int limitW = 960, limitH = 540;
        boolean quickResize;""")
edit(streamer,
"""            width = x1 - x0;
            height = y1 - y0;
            long row = width * 4L, bytes = row * height;
            if (bytes > capacity) {
                buffer = buffer == 0 ? MemoryUtil.nmemAlloc(bytes) : MemoryUtil.nmemRealloc(buffer, bytes);
                capacity = bytes;
            }
            if (width == w) {
                MemoryUtil.memCopy(address + (long) y0 * w * 4, buffer, bytes);
            } else {
                for (int r = 0; r < height; r++) MemoryUtil.memCopy(address + ((long) (y0 + r) * w + x0) * 4, buffer + r * row, row);
            }""",
"""            int sourceW = x1 - x0, sourceH = y1 - y0;
            if (quickResize && sourceW > 0 && sourceH > 0) {
                double factor = Math.min(1.0, Math.sqrt((double) limitW * limitH / ((double) sourceW * sourceH)));
                width = Math.max(1, (int)Math.round(sourceW * factor));
                height = Math.max(1, (int)Math.round(sourceH * factor));
            } else {
                width = sourceW;
                height = sourceH;
            }
            long row = width * 4L, bytes = row * height;
            if (bytes > capacity) {
                buffer = buffer == 0 ? MemoryUtil.nmemAlloc(bytes) : MemoryUtil.nmemRealloc(buffer, bytes);
                capacity = bytes;
            }
            if (width == sourceW && height == sourceH) {
                if (width == w) {
                    MemoryUtil.memCopy(address + (long)y0 * w * 4, buffer, bytes);
                } else {
                    for (int r = 0; r < height; r++)
                        MemoryUtil.memCopy(address + ((long)(y0+r)*w+x0)*4, buffer + r*row, row);
                }
            } else {
                // Nearest-neighbour fast path: bounded O(output pixels) and zero extra allocations.
                double dx = sourceW / (double) width;
                double dy = sourceH / (double) height;
                for (int yy = 0; yy < height; yy++) {
                    int srcY = y0 + Math.min(sourceH-1,(int)((yy+0.5)*dy));
                    long srcRow = address + ((long)srcY*w + x0)*4;
                    long dstRow = buffer + (long)yy*row;
                    for (int xx = 0; xx < width; xx++) {
                        int srcX = Math.min(sourceW-1,(int)((xx+0.5)*dx));
                        MemoryUtil.memPutInt(dstRow + xx*4L,MemoryUtil.memGetInt(srcRow + srcX*4L));
                    }
                }
            }""")

# Windows Graphics Capture remains async, but a 240Hz video no longer forces
# 240 native captures or GL uploads each second just because the screen is visible.
win = "core/src/main/java/com/desktopscreens/core/WindowCapture.java"
edit(win, "    private volatile boolean running = true;",
          "    private volatile boolean running = true;\n    private volatile int maxFps = 60;")
edit(win,
"""    @Override
    public void close() {
        running = false;
    }""",
"""    /** Change the capture budget without recreating the Windows capture session. */
    public void setMaxFps(int fps) { maxFps = Math.max(5, Math.min(120, fps)); }

    @Override
    public void close() {
        running = false;
    }""")
edit(win,
"""            while (running) {
                long now = System.nanoTime();""",
"""            long nextCapture = 0;
            while (running) {
                long now = System.nanoTime();
                if (now < nextCapture) {
                    Thread.sleep(Math.max(1L, Math.min(8L, (nextCapture - now)/1_000_000L)));
                    continue;
                }
                nextCapture = now + 1_000_000_000L / maxFps;""")

monitor = "core/src/main/java/com/desktopscreens/core/DesktopCapture.java"
edit(monitor, "    private volatile boolean running = true, drawCursor = true, duplicationAllowed = true, duplicating, paused, protectedContent;",
       "    private volatile boolean running = true, drawCursor = true, duplicationAllowed = true, duplicating, paused, protectedContent;\n    private volatile int maxFps = 60;")
edit(monitor,
"""    @Override
    public void close() {
        running = false;
    }""",
"""    /** Capture budget: this is asynchronous and does not delay game rendering. */
    public void setMaxFps(int fps) { maxFps = Math.max(5, Math.min(120, fps)); }

    @Override
    public void close() {
        running = false;
    }""")
edit(monitor,
"""            boolean wasPaused = false;
            while (running) {""",
"""            boolean wasPaused = false;
            long nextCapture = 0;
            while (running) {""")
edit(monitor,
"""                long now = System.nanoTime();
                boolean allowed = duplicationAllowed;""",
"""                long now = System.nanoTime();
                if (now < nextCapture) {
                    Thread.sleep(Math.max(1L, Math.min(8L, (nextCapture - now)/1_000_000L)));
                    continue;
                }
                nextCapture = now + 1_000_000_000L / maxFps;
                boolean allowed = duplicationAllowed;""")

# Set caps at capture startup and update them only on regular game ticks.
live_window=client+"LiveWindow.java"
edit(live_window,
"""        capture = new WindowCapture(window.handle(), window.toString(), graphicsCaptureAllowed(mc),
                message -> DesktopScreens.LOG.info("Capture: {}", message));""",
"""        capture = new WindowCapture(window.handle(), window.toString(), graphicsCaptureAllowed(mc),
                message -> DesktopScreens.LOG.info("Capture: {}", message));
        capture.setMaxFps(HostPerformance.captureFps(mc));""")
edit(live_window,
"""        for (LiveWindow live : OPEN.values()) live.capture.setGraphicsCaptureAllowed(allowed);""",
"""        for (LiveWindow live : OPEN.values()) {
            live.capture.setGraphicsCaptureAllowed(allowed);
            live.capture.setMaxFps(HostPerformance.captureFps(mc));
        }""")

live_monitor=client+"LiveCapture.java"
edit(live_monitor,
"""        for (LiveCapture live : OPEN.values()) live.allowDuplication(live.capture);""",
"""        for (LiveCapture live : OPEN.values()) {
            live.capture.setMaxFps(HostPerformance.captureFps(live.mc));
            live.allowDuplication(live.capture);
        }""")
edit(live_monitor,
"""        DesktopCapture c = new DesktopCapture(monitor, DesktopConfig.fastCapture, message -> DesktopScreens.LOG.info("Capture: {}", message));""",
"""        DesktopCapture c = new DesktopCapture(monitor, DesktopConfig.fastCapture, message -> DesktopScreens.LOG.info("Capture: {}", message));
        c.setMaxFps(HostPerformance.captureFps(mc));""")

world=client+"WorldScreens.java"
edit(world,
"""        long frameKey = Long.MIN_VALUE, lastWanted, sourceCheckedAt;""",
"""        long frameKey = Long.MIN_VALUE, lastWanted, sourceCheckedAt, lastUploadedAt;""") if False else None
# V5 still contains 'long frameKey' without the above leading spaces on some versions.
edit(world,"        long frameKey = Long.MIN_VALUE, lastWanted, sourceCheckedAt;",
           "        long frameKey = Long.MIN_VALUE, lastWanted, sourceCheckedAt, lastUploadedAt;")
edit(world,
"""        view.frameKey = key;
        view.picture = null;
        long now = System.nanoTime();
        view.lastWanted = now;""",
"""        view.frameKey = key;
        long now = System.nanoTime();
        view.lastWanted = now;
        // Never upload a full-resolution texture hundreds of times each second.
        // All blocks showing the same source reuse this one cached GPU texture.
        if (view.picture != null && HostPerformance.active(mc)
                && now - view.lastUploadedAt < HostPerformance.uploadIntervalNs(mc)) return view.picture;
        view.lastUploadedAt = now;
        view.picture = null;""")

# Simple, persistent UI preset switch without exposing sensitive window/process names.
gui=client+"BroadcastMenu.java"
edit(gui,"    private Button go,audio;","    private Button go,audio,performance;")
edit(gui,
"""        addRenderableWidget(Theme.button(x,y+92,250,22,"RETOUR",b->onClose()));""",
"""        performance=addRenderableWidget(Theme.button(x,y+90,250,24,
            "PERFORMANCE : "+HostPerformance.profileName(),b->{
            DesktopConfig.performanceProfile=(DesktopConfig.performanceProfile+1)%3;
            DesktopConfig.save();
            b.setMessage(Component.literal("PERFORMANCE : "+HostPerformance.profileName()));
        }));
        addRenderableWidget(Theme.button(x,y+120,250,22,"RETOUR",b->onClose()));""")
edit(gui,
"""        audio.setMessage(Component.literal(DesktopConfig.shareSound?"SON : OUI":"SON : NON"));""",
"""        audio.setMessage(Component.literal(DesktopConfig.shareSound?"SON : OUI":"SON : NON"));
        if(performance!=null)performance.setMessage(Component.literal("PERFORMANCE : "+HostPerformance.profileName()));""")
edit(gui,
"""        g.drawCenteredString(font,"Tablette : clic droit pour choisir",width/2,height/2+100,Theme.PLUM);""",
"""        g.drawCenteredString(font,"Tablette : clic droit pour choisir",width/2,height/2+105,Theme.PLUM);
        g.drawCenteredString(font,HostPerformance.diagnostic(minecraft),width/2,height/2+119,Theme.INK);""")

print("V6 patches applied: hardware capture caps, per-source upload rate limits, reduced stream encoder CPU/bandwidth, adaptive host profile.")
