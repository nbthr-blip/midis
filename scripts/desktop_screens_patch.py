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

print("Bootstrap patch applied: 1.21.11 Fabric target, modern rendering API, apostrophe settings key.")

