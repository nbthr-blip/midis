#!/usr/bin/env python3
"""Experimental V5: fix 180-degree tablet video, consistent beige/plum menus,
and explicit exact Windows-window selection on each existing Minecraft screen.
Run after V4 feature scripts, before Stonecutter/Gradle compile.
"""
from pathlib import Path
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

def load(path):
    return (ROOT / path).read_text(encoding="utf-8")
def save(path, data):
    out = ROOT / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(data, encoding="utf-8")
def replace(path, old, new):
    data = load(path)
    if old not in data:
        raise SystemExit("V5 missing exact anchor: " + path + ": " + repr(old[:120]))
    save(path, data.replace(old, new, 1))

# The tablet mesh is already oriented toward the player. Its VIDEO was rotated 180 degrees.
# Correct the texture UV, NOT the 3D mesh or the player's arms.
tablet = "src/main/java/com/desktopscreens/client/HeldTablet.java"
replace(tablet, """            Vertices.picture(out,m,x1,y0,z,u1,v1,0xFFFFFFFF);
            Vertices.picture(out,m,x0,y0,z,u0,v1,0xFFFFFFFF);
            Vertices.picture(out,m,x0,y1,z,u0,v0,0xFFFFFFFF);
            Vertices.picture(out,m,x1,y1,z,u1,v0,0xFFFFFFFF);""",
"""            // The map-style two-handed pose rotates the device by 180 degrees.
            // Reverse BOTH UV axes to make the moving Windows picture upright.
            Vertices.picture(out,m,x1,y0,z,u0,v0,0xFFFFFFFF);
            Vertices.picture(out,m,x0,y0,z,u1,v0,0xFFFFFFFF);
            Vertices.picture(out,m,x0,y1,z,u1,v1,0xFFFFFFFF);
            Vertices.picture(out,m,x1,y1,z,u0,v1,0xFFFFFFFF);""")

# Enumerate actual top-level application windows, including two windows of the same program.
# Labels are NEVER sent to the network or saved. Unique window handles ARE saved per screen.
apps = "core/src/main/java/com/desktopscreens/core/AppWindow.java"
replace(apps, "    /** The app window at a point on the desktop, or null if there's none (the desktop, the taskbar, a menu...). */",
"""    /** Visible app windows, front-most first. Only the local Windows host can read their titles. */
    public static List<AppWindow> list() {
        final List<AppWindow> result = new ArrayList<>();
        User32.INSTANCE.EnumWindows(new WinUser.WNDENUMPROC() {
            @Override
            public boolean callback(HWND w, Pointer data) {
                if (isAppWindow(w) && !cloaked(w)) {
                    AppWindow window = new AppWindow(w);
                    if (window.handle() != 0L) result.add(window);
                }
                return true;
            }
        }, null);
        return result;
    }

    /** The app window at a point on the desktop, or null if there's none (the desktop, the taskbar, a menu...). */""")

# Source chooser stays IN the active DesktopScreen to keep its capture session open.
# Opening a separate Minecraft Screen would close DesktopScreen and its Windows capture.
menu = "src/main/java/com/desktopscreens/client/DesktopScreen.java"
replace(menu, "private enum Mode { DESKTOP, SETTINGS, SHARING, PIP, STREAM, BORDER }",
       "private enum Mode { DESKTOP, SETTINGS, WINDOWS, SHARING, PIP, STREAM, BORDER }")
replace(menu, "    private SharingPage sharingPage;",
       "    private SharingPage sharingPage;\n    /** Current page in the host-only local Windows window picker. */\n    private int windowPage;")
replace(menu, "        if (mode == Mode.SETTINGS) addSettingsWidgets();",
       "        if (mode == Mode.SETTINGS) addSettingsWidgets();\n        else if (mode == Mode.WINDOWS) addWindowWidgets();")

# Replace the old source cycle (monitors + currently selected window only) with
# a clear "CHOOSE A WINDOW" navigation button. On screen mode it updates THAT screen.
s = load(menu)
start_key = "        // The monitors, and first the one window shown, if there is one. Windows are picked with Right Ctrl + W."
end_key = "        y += 22;\n        //? if >=26.1 {"
if start_key not in s or end_key not in s:
    raise SystemExit("V5 could not locate source-cycle block in DesktopScreen.java")
start=s.index(start_key)
end=s.index(end_key,start)
s=s[:start] + """        // The source may be one SPECIFIC Windows app window, not just an entire monitor.
        // A dedicated page lists every visible window, including multiple Chrome windows.
        String sourceName = session.window() != null
                ? "FENETRE : " + session.window().label()
                : "MONITEUR : " + session.target().shortLabel();
        String displayed = font.plainSubstrByWidth(sourceName, w - 12);
        addRenderableWidget(Button.builder(Component.literal(displayed + " >"), button -> {
            windowPage = 0;
            switchTo(Mode.WINDOWS);
        }).bounds(x, y, w, 20)
          .tooltip(Tooltip.create(Component.literal("Choisir exactement une fenetre ou un moniteur pour cet ecran"))).build());
""" + s[end:]
save(menu,s)

# The list includes monitors AND each distinct application window.
# For an active screen, DesktopSession.choice is already a copy of that specific screen's SourceChoice.
insertion="""    /** A privacy-conscious source picker for each existing screen, with pageable Windows window list. */
    private void addWindowWidgets() {
        int x = PAD, w = PANEL_WIDTH - 2 * PAD;
        List<Source> options = new ArrayList<>();
        for (Monitor mon : Monitors.list()) options.add(new Source(mon, null));
        for (AppWindow app : AppWindow.list()) {
            Monitor monitor = Monitors.of(app.handle());
            if (monitor != null) options.add(new Source(monitor, app));
        }
        int each = Math.max(3, Math.min(6, (height - 106) / 23));
        if (windowPage * each >= options.size()) windowPage = Math.max(0, (options.size()-1) / each);
        int start = windowPage * each;
        int y = 23;
        for (int i = start; i < Math.min(options.size(), start + each); i++) {
            Source source = options.get(i);
            String name = source.window() != null
                ? "FENETRE : " + source.window().label()
                : "ECRAN ENTIER : " + source.monitor().shortLabel();
            String shortName = font.plainSubstrByWidth(name, w - 10);
            addRenderableWidget(Button.builder(Component.literal(shortName), button -> {
                if (source.window() != null) {
                    if (!source.window().alive()) {
                        windowPage = 0;
                        rebuildWidgets();
                        return;
                    }
                    session.setWindow(source.window());
                } else {
                    setMonitor(source.monitor());
                }
                DesktopConfig.save();
                switchTo(Mode.SETTINGS);
            }).bounds(x, y, w, 21)
              .tooltip(Tooltip.create(Component.literal(
                    source.window() != null ? source.window().label() + " (" + source.window().exe + ")" :
                    "Capturer tout " + source.monitor().label()))).build());
            y += 23;
        }

        int bottom = height - 72;
        int half = (w - 5)/2;
        if (windowPage > 0) {
            addRenderableWidget(Button.builder(Component.literal("< PRECEDENT"), button -> {
                windowPage--;
                rebuildWidgets();
            }).bounds(x, bottom, half, 20).build());
        }
        if (start + each < options.size()) {
            addRenderableWidget(Button.builder(Component.literal("SUIVANT >"), button -> {
                windowPage++;
                rebuildWidgets();
            }).bounds(x + w-half, bottom, half, 20).build());
        }
        addRenderableWidget(Button.builder(Component.literal("ACTUALISER LES FENETRES"), button ->
                rebuildWidgets()).bounds(x, height - 48, w, 20).build());
        addRenderableWidget(Button.builder(Component.literal("RETOUR AUX PARAMETRES"), button ->
                switchTo(Mode.SETTINGS)).bounds(x, height - 24, w, 20).build());
    }

"""
replace(menu, "    /** The border's style, on the settings and on its page", insertion + "    /** The border's style, on the settings and on its page")

# The regular GUI escape flow must recognize the extra subpage.
replace(menu, "mode == Mode.SHARING || mode == Mode.PIP || mode == Mode.STREAM || mode == Mode.BORDER",
       "mode == Mode.SHARING || mode == Mode.WINDOWS || mode == Mode.PIP || mode == Mode.STREAM || mode == Mode.BORDER")

# Beige settings sidebar, violet title band, pleasant contrast for every SETTINGS/PIP/STREAM/SHARING/BORDER/WINDOWS page.
replace(menu, """            g.fill(0, 0, PANEL_WIDTH, height, 0xFF161616);
            if (mode == Mode.SETTINGS) {""",
"""            g.fillGradient(0, 0, PANEL_WIDTH, height, 0xFFF4E9D9, 0xFFE8D7CD);
            g.fillGradient(0, 0, PANEL_WIDTH, 19, 0xFF78549D, 0xFF50356F);
            g.fill(0, 19, PANEL_WIDTH, 20, 0xFFD1A7D7);
            if (mode == Mode.WINDOWS) {
                GuiDraw.text(g, font, Component.literal("SOURCE DE L'ECRAN"), PAD, 6, 0xFFFFFF);
                GuiDraw.text(g, font, Component.literal("Une fenetre OU un moniteur"), PAD, height - 93, 0xFF59446F);
            } else if (mode == Mode.SETTINGS) {""")
replace(menu,"pageTextY + i * (font.lineHeight + 1), 0xB0B0B0",
             "pageTextY + i * (font.lineHeight + 1), 0xFF4C3B59")
replace(menu, "DesktopConfig.borderStyle == BorderStyle.SOLID ? 0xE0E0E0 : 0x707070",
              "DesktopConfig.borderStyle == BorderStyle.SOLID ? 0xFF443654 : 0xFF8F8493")
# The source picker note should never print a sensitive title on the network.
# It is only a local UI list queried from Win32.

# Local sharing page text colors for the now-beige background.
share = "src/main/java/com/desktopscreens/client/SharingPage.java"
s=load(share)
start=s.index("    void render(GuiGraphics g, Font font, int x) {")
stop=s.index("    /**",start)
block=s[start:stop].replace("0xB0B0B0","0xFF5F4A69").replace("0xE0E0E0","0xFF3F3451").replace("0xFFFFFF","0xFF3B2A46")
save(share,s[:start]+block+s[stop:])

# Style the REAL Minecraft vanilla buttons/cycles used in the original advanced settings panel,
# not just V4's custom initial screen. Controls remain keyboard- and controller-accessible.
save("src/main/java/com/desktopscreens/mixin/AdvancedSettingsButtonThemeMixin.java", """package com.desktopscreens.mixin;

import com.desktopscreens.client.DesktopScreen;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractButton;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(AbstractButton.class)
abstract class AdvancedSettingsButtonThemeMixin {
    @Inject(method = "renderDefaultSprite", at = @At("HEAD"), cancellable = true)
    private void desktopscreens$themedButton(GuiGraphics g, CallbackInfo ci) {
        if (!(Minecraft.getInstance().screen instanceof DesktopScreen)) return;
        AbstractButton b = (AbstractButton)(Object)this;
        int x = b.getX(), y = b.getY(), w = b.getWidth(), h = b.getHeight();
        int light = !b.active ? 0xFFABA0B6 : b.isHoveredOrFocused() ? 0xFF9A70BF : 0xFF6E4A8F;
        int dark  = !b.active ? 0xFF8F849E : b.isHoveredOrFocused() ? 0xFF78509D : 0xFF4E3766;
        g.fillGradient(x, y, x + w, y + h, light, dark);
        g.renderOutline(x, y, w, h, b.isHoveredOrFocused() ? 0xFFEEDAF4 : 0xFFB995D1);
        ci.cancel();
    }
}
""")
# Register without interfering with other Minecraft UI mods.
replace("src/main/resources/desktopscreens.mixins.json",
        '    "ItemInHandRendererMixin",',
        '    "ItemInHandRendererMixin",\n    "AdvancedSettingsButtonThemeMixin",')

# Style all original IntSlider rows on every advanced page, preserving their values and drag handling.
slider = "src/main/java/com/desktopscreens/client/IntSlider.java"
replace(slider, "import net.minecraft.client.gui.components.AbstractSliderButton;",
               "import net.minecraft.client.gui.components.AbstractSliderButton;\nimport net.minecraft.client.gui.GuiGraphics;\nimport net.minecraft.client.Minecraft;")
replace(slider, """    private int intValue() {""",
"""    @Override
    public void renderWidget(GuiGraphics g, int mouseX, int mouseY, float partialTicks) {
        if (!(Minecraft.getInstance().screen instanceof DesktopScreen)) {
            super.renderWidget(g, mouseX, mouseY, partialTicks);
            return;
        }
        int x = getX(), y = getY(), w = getWidth(), h = getHeight();
        g.fillGradient(x, y, x+w, y+h, 0xFF80629E, 0xFF503768);
        int knob = x + (int)(Math.max(0, Math.min(1, this.value)) * (w - 8));
        g.fill(knob, y + 1, knob + 8, y + h - 1, 0xFFE8D1B7);
        g.drawCenteredString(Minecraft.getInstance().font, getMessage(), x+w/2, y+h/2-4, 0xFFFFFFFF);
    }

    private int intValue() {""")

# A virtual host desktop stream would bypass per-screen window selection: remove that menu choice.
channels = "src/main/java/com/desktopscreens/client/TabletChannels.java"
replace(channels,
        '        choices.add(new Channel(host,HostBroadcast.STREAM_ID,HostBroadcast.WATCH_POS,"Bureau de l\\'hote"));\n',
        '        // Tablets list ONLY explicitly built screens, not an undisclosed whole-desktop feed.\n')

print("V5 patches applied: 180-degree UV correction, enumerate exact Win32 windows, per-screen GUI selector, beige/plum advanced settings.")
