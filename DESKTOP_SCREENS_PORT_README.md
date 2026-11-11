# Desktop Screens — Fabric 1.21.11 (experimental port)

This is a **development bootstrap**, not a finished mod. No playable JAR has been verified.

## Goal
Port [MagiMigi/desktop-screens](https://github.com/MagiMigi/desktop-screens) (MIT) to Minecraft Java 1.21.11 Fabric, retain its original 3D models/textures, screen/tablet, application-window capture and shared audio/video, and test multiplayer with Essential's integrated server. No VPS or paid relay.

## Build
The workflow clones the upstream project, runs `scripts/desktop_screens_patch.py` and attempts `:1.21.11-fabric:build`. Expect compiler/API migration errors until the port is completed. A green build is necessary but **not sufficient** to prove compatibility.

## Shortcut
The bootstrap binds the **settings** key to apostrophe (`'`) as a starting point. It does not yet implement StreamCraft's exact menu or every interaction. Original Desktop Screens uses **G** to use screens.

## Required validation
1. Successful Fabric 1.21.11 compilation and client launch.
2. Blocks, screen-builder and tablet render using original assets.
3. Capture and select a Windows application.
4. Audio/video shared across two real Minecraft clients.
5. Essential-hosted world tested with multiple players.
6. Sound attenuation and reconnection after host restart.

## Status
- [x] Upstream project and build layout inspected.
- [x] Experimental GitHub branch and workflow created.
- [x] Initial version and shortcut bootstrap patch.
- [ ] Compile verified.
- [ ] Real multiplayer verified.
- [ ] Release JAR.

The source is MIT licensed by MagiMigi. Keep upstream copyright and license notices.
