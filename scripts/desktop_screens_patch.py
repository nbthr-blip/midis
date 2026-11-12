#!/usr/bin/env python3
"""Port bootstrap for Desktop Screens 0.3.5 -> Minecraft 1.21.11 Fabric.
Based on MagiMigi/desktop-screens (MIT); not a tested full port.
Run at the root of a fresh upstream checkout.
"""
from pathlib import Path

import sys
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

def replace(path, before, after):
    file = ROOT / path
    old = file.read_text(encoding="utf-8")
    if before not in old:
        raise SystemExit(f"Patch anchor missing: {path}: {before[:90]}")
    file.write_text(old.replace(before, after, 1), encoding="utf-8")

replace("settings.gradle.kts",
        '        match("1.21.1", "fabric", "neoforge")',
        '        match("1.21.1", "fabric", "neoforge")\n        match("1.21.11", "fabric")')

props = '''["1.21.11"]
java = "21"
mod.minecraft_range = "[1.21.11]"
mod.pack_format = "75"
mod.data = "1.21.1 1.21.11"

[fabric."1.21.11"]
deps.fabric_api = "0.141.6+1.21.11"
deps.fabric_loader = "0.19.5"
deps.fabric_loader_min = "0.18.0"
deps.modmenu = "17.0.1"
deps.common_protection = "1.0.0"
deps.architectury = "19.0.1"
deps.opac = "fabric-1.21.11-0.31.6"
deps.ftb_chunks = "2101.1.22"
deps.forge_config_api_port = "v21.1.6-1.21.1-Fabric"
deps.flan = "1.21.1-1.12.8-fabric"

'''
replace("stonecutter.properties.toml", '["26.1.2"]', props + '["26.1.2"]')
replace("build.fabric.gradle.kts",
        '''    if (sc.current.parsed < "26.1") mappings(loom.layered {
        officialMojangMappings()
        parchment("org.parchmentmc.data:parchment-${prop("deps.parchment_minecraft")}:${prop("deps.parchment")}@zip")
    })''',
        '''    if (minecraft == "1.21.11") {
        mappings(loom.officialMojangMappings())
    } else if (sc.current.parsed < "26.1") mappings(loom.layered {
        officialMojangMappings()
        parchment("org.parchmentmc.data:parchment-${prop("deps.parchment_minecraft")}:${prop("deps.parchment")}@zip")
    })''')
replace("gradle.properties", 'version=0.3.5', 'version=0.3.5+mc1.21.11-custom.1')
replace("src/main/java/com/desktopscreens/client/DesktopClient.java",
        '"key.desktopscreens.settings", InputConstants.Type.KEYSYM, InputConstants.UNKNOWN.getValue(), CATEGORY);',
        '"key.desktopscreens.settings", InputConstants.Type.KEYSYM, GLFW.GLFW_KEY_APOSTROPHE, CATEGORY);')
# 1.21.9+ resource packs need min_format/max_format instead of pack_format.
(ROOT / "src/main/resources/pack.mcmeta").write_text('''{
  "pack": {
    "description": "Desktop Screens resources",
    "min_format": [75, 0],
    "max_format": [75, 0]
  }
}
''', encoding="utf-8")
# Item definitions were introduced before 1.21.11; preserve the original models and use the
# source project's later-version item definitions.
for name in ("screen", "tablet", "screen_builder"):
    source = ROOT / "src/data/26.1/assets/desktopscreens/items" / f"{name}.json"
    dest = ROOT / "src/data/1.21.11/assets/desktopscreens/items" / f"{name}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())

# Minecraft 1.21.9 introduced the modern render-state APIs; upstream only switches
# to those implementations at 26.1. Enable the 26.1 paths for 1.21.11 here.
# This is an experimental API migration, not a guarantee of runtime compatibility.
for source in (ROOT / "src/main/java").rglob("*.java"):
    body = source.read_text(encoding="utf-8")
    migrated = body.replace(">=26.1", ">=1.21.11").replace("<26.1", "<1.21.11")
    if migrated != body:
        source.write_text(migrated, encoding="utf-8")


# 1.21.11 has the GUI draw-state model, but NOT the 26.1 names or some 26.1-only APIs.
def edit_java(name, substitutions):
    matches = list((ROOT / "src/main/java").rglob(name))
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {name}, found {len(matches)}")
    file = matches[0]
    src = file.read_text(encoding="utf-8")
    for old, new in substitutions:
        if old not in src:
            raise SystemExit(f"Missing {name} anchor: {old[:90]}")
        src = src.replace(old, new)
    file.write_text(src, encoding="utf-8")

# 1.21.11 GUI state types are in client.gui.render.state, not renderer.state.gui.
for file in (ROOT / "src/main/java").rglob("*.java"):
    src = file.read_text(encoding="utf-8")
    out = src.replace("net.minecraft.client.renderer.state.gui.", "net.minecraft.client.gui.render.state.")
    out = out.replace("net.minecraft.client.renderer.state.level.CameraRenderState",
                      "net.minecraft.client.renderer.state.CameraRenderState")
    if out != src:
        file.write_text(out, encoding="utf-8")

# Fabric has still the old block-color event and a renamed world render event in 1.21.11.
edit_java("DesktopScreensFabricClient.java", [
    ("import net.fabricmc.fabric.api.client.rendering.v1.BlockColorRegistry;",
     "import net.fabricmc.fabric.api.client.rendering.v1.ColorProviderRegistry;"),
    ("import net.minecraft.client.color.block.BlockTintSource;", ""),
    ("import net.fabricmc.fabric.api.client.rendering.v1.level.LevelRenderEvents;",
     "import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderEvents;"),
    ("BlockColorRegistry.register(List.<BlockTintSource>of(state -> ScreenFrames.tint(0), state -> ScreenFrames.tint(1),\n                state -> ScreenFrames.tint(2), state -> ScreenFrames.tint(3)), DesktopScreensFabric.screen);",
     "ColorProviderRegistry.BLOCK.register((state, level, pos, tintIndex) -> ScreenFrames.tint(tintIndex), DesktopScreensFabric.screen);"),
    ("LevelRenderEvents.END_MAIN.register(context -> DesktopClient.renderWorld(context.levelState().cameraRenderState.pos));",
     "WorldRenderEvents.END_MAIN.register(context -> DesktopClient.renderWorld(context.worldState().cameraRenderState.pos));")
])

# FTB's 26.1 new claims API does not exist in 1.21.11: leave legacy Architectury integration.
for name in ("ClaimMods.java", "LandClaimsFabric.java"):
    file = ROOT / "src/main/java/com/desktopscreens/fabric" / name
    src = file.read_text(encoding="utf-8")
    src = src.replace(">=1.21.11", ">=26.1")
    if name == "ClaimMods.java":
        # bundled Common Protection API 1.0 expects GameProfile here
        src = src.replace("player.nameAndId(), player", "player.getGameProfile(), player")
    file.write_text(src, encoding="utf-8")

# Mojang mappings changes between 1.21.1 -> 1.21.11.
edit_java("Players.java", [("player.sendOverlayMessage(message)", "player.displayClientMessage(message, true)")])
edit_java("LiveCapture.java", [("mc.getToasts()", "mc.getToastManager()")])
edit_java("SharingData.java", [
    ('new SavedDataType<>(DesktopScreens.id("sharing"), SharingData::new, CODEC, null)',
     'new SavedDataType<>(NAME, SharingData::new, CODEC, null)')
])
edit_java("SharedSounds.java", [("mc.gameRenderer.getMainCamera().getPosition()", "mc.gameRenderer.getMainCamera().position()")])
edit_java("ScreenBuilderClient.java", [("mc.getTimer().getGameTimeDeltaPartialTick(true)",
                                      "mc.getDeltaTracker().getGameTimeDeltaPartialTick(true)")])
edit_java("CameraGlide.java", [("return camera.getFov();", "return mc.options.fov().get();")])
for name in ("WorldBar.java", "GameCover.java"):
    edit_java(name, [("import net.minecraft.util.LightCoordsUtil;",
                      "import net.minecraft.client.renderer.LightTexture;"),
                     ("LightCoordsUtil.FULL_BRIGHT", "LightTexture.FULL_BRIGHT")])
edit_java("GuiDraw.java", [("g.text(font, text, x, y, opaque(color), shadow);",
                           "g.drawString(font, text, x, y, opaque(color), shadow);")])
edit_java("ColorSwatch.java", [("protected void extractContents(GuiGraphics g, int mouseX, int mouseY, float partialTick)",
                              "protected void renderContents(GuiGraphics g, int mouseX, int mouseY, float partialTick)")])
edit_java("DesktopScreen.java", [
    ("public void extractBackground(GuiGraphics g, int mouseX, int mouseY, float partialTick)",
     "public void renderBackground(GuiGraphics g, int mouseX, int mouseY, float partialTick)"),
    ("public void extractRenderState(GuiGraphics g, int mouseX, int mouseY, float partialTick)",
     "public void render(GuiGraphics g, int mouseX, int mouseY, float partialTick)"),
    ("super.extractRenderState(g, mouseX, mouseY, partialTick);",
     "super.render(g, mouseX, mouseY, partialTick);")
])
# Picture render pipeline 26.1 used newer depth APIs unavailable in 1.21.11.
edit_java("PictureRenderType.java", [
    ("import com.mojang.blaze3d.pipeline.DepthStencilState;",
     "import com.mojang.blaze3d.platform.DepthTestFunction;"),
    ("import com.mojang.blaze3d.platform.CompareOp;", ""),
    ("new DepthStencilState(CompareOp.LESS_THAN_OR_EQUAL, true, -1.0F, -10.0F)",
     "DepthTestFunction.LEQUAL_DEPTH_TEST"),
    (".withDepthStencilState(DepthTestFunction.LEQUAL_DEPTH_TEST)",
     ".withDepthTestFunction(DepthTestFunction.LEQUAL_DEPTH_TEST).withDepthBias(-1.0F, -10.0F)")
])


# 1.21.11 GUI model accepts SimpleGuiElementRenderState via addSimpleElement.
edit_java("GuiDraw.java", [(".addGuiElement(element)", ".addSimpleElement(element)")])


# On 1.21.11 (Mojang mappings), GuiRenderState submits a GuiElementRenderState this way:
edit_java("GuiDraw.java", [(".addSimpleElement(element)", ".submitGuiElement(element)")])

# Some Stonecutter-generated 1.21.11 files still contain older code even when the source
# was changed. Fix these exact expressions at compile time, after Stonecutter generates them.
# Fail fast if the generated source directory is not found.
(ROOT / "build.fabric.gradle.kts").open("a", encoding="utf-8").write("""
tasks.named<JavaCompile>("compileJava") {
    doFirst {
        val javaDir = project.layout.buildDirectory.dir("generated/stonecutter/main/java").get().asFile
        if (!javaDir.exists()) throw GradleException("Stonecutter's generated Java not found: $javaDir")
        val changes = listOf(
            Triple("com/desktopscreens/client/LiveCapture.java", "mc.getToasts()", "mc.getToastManager()"),
            Triple("com/desktopscreens/client/ScreenBuilderClient.java", "mc.getTimer()", "mc.getDeltaTracker()"),
            Triple("com/desktopscreens/client/SharedSounds.java", "mc.gameRenderer.getMainCamera().getPosition()", "mc.gameRenderer.getMainCamera().position()")
        )
        for ((path, old, replacement) in changes) {
            val file = javaDir.resolve(path)
            val before = file.readText()
            if (before.contains(old)) {
                file.writeText(before.replace(old, replacement))
                println("1.21.11 generated code fixed: $path")
            }
        }
    }
}
""")

print("Compatibility patch applied for the Fabric 1.21.11 GUI, renderer, and Mojang API migrations.")




