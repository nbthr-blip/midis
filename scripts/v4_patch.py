#!/usr/bin/env python3
"""Desktop Screens 1.21.11 V4 experimental feature patch.
Apply after desktop_screens_patch.py, host_broadcast_patch.py, host_broadcast_stage3.py.
"""
from pathlib import Path
import sys, json
R=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()
def read(p): return (R/p).read_text("utf-8")
def put(p,s):
 f=R/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s,"utf-8")
def rep(p,a,b):
 s=read(p)
 if a not in s:raise RuntimeError("V4 anchor missing "+p+": "+a[:130])
 put(p,s.replace(a,b,1))
# IMPORTANT: The V2 broadcast override forced every TV to show the SAME desktop.
# Restore the original owner-specific window selection on physical screens.
p="src/main/java/com/desktopscreens/client/ScreenRenderer.java";s=read(p)
a="        UUID host = SharingInfo.broadcastHost();\n        if (!HostBroadcast.NO_HOST.equals(host)) {"
b="        if (owner == null) return hintOnly(group, screen, state, hint);"
if a not in s or b not in s:raise RuntimeError("Missing prior renderer anchors")
s=s[:s.index(a)]+s[s.index(b):]
s=s.replace("import com.desktopscreens.HostBroadcast;\n","")
put(p,s)

# Never replace a sound subscription merely because a different screen plays too.
p="src/main/java/com/desktopscreens/client/ShareWatching.java"
rep(p, """        for (Map.Entry<Screen, Interest> e : INTERESTS.entrySet()) {
            Interest other = e.getValue();
            if (e.getKey().owner().equals(screen.owner()) && !e.getKey().equals(screen) && now - other.soundAt < SOUND_LINGER_NANOS) {
                other.soundAt = now - SOUND_LINGER_NANOS - 1;
            }
        }
""","")

# Different programs are ALREADY captured separately by ShareSound.
# Decode by (owner, stream ID) instead of only (owner) to play several simultaneously.
p="src/main/java/com/desktopscreens/client/SharedSounds.java"
s=read(p);start=s.index("    private static final Map<UUID, Listening> LISTENING")
end=s.index("    private static void startPump() {",start)
replacement="""    private record AudioKey(UUID owner,int stream) {}
    private record ScreenKey(UUID owner,UUID id) {}
    private static final Map<AudioKey, Listening> LISTENING = new ConcurrentHashMap<>();
    private static volatile Map<ScreenKey,Near> near=Map.of();
    private static Thread pump;
    private SharedSounds() {}
    private record Near(BlockPos anchor,UUID id,Vec3 point,double distance) {}

    static void sound(ShareStream.Sound packet) {
        Near best=null;
        Map<ScreenKey,Near> current=near;
        for(UUID id:packet.screens()) {
            Near candidate=current.get(new ScreenKey(packet.owner(),id));
            if(candidate!=null && (best==null || candidate.distance()<best.distance())) best=candidate;
        }
        if(best==null)return;
        AudioKey key=new AudioKey(packet.owner(),packet.stream());
        Listening l=LISTENING.get(key);
        if(l==null) {
            Listening newcomer=new Listening(packet.owner(),packet.owner().toString().substring(0,8));
            Listening previous=LISTENING.putIfAbsent(key,newcomer);
            l=previous==null?newcomer:previous;
            if(previous==null) startPump();
        }
        l.near=best;
        l.screen=best.id();
        l.packets.add(packet);
        l.lastPacketAt=System.nanoTime();
    }

    static void tick(Minecraft mc) {
        ClientPacketListener connection=mc.getConnection();
        if(mc.level==null || mc.player==null || connection==null) {
            near=Map.of();
            for(Listening l:LISTENING.values())l.close(mc);
            LISTENING.clear();
            return;
        }
        DesktopConfig.load();
        boolean audible=mc.options.getSoundSourceVolume(SoundSource.MASTER)>0
                && mc.options.getSoundSourceVolume(SoundSource.RECORDS)>0;
        near=audible?scan(mc,connection):Map.of();
        long now=System.nanoTime();
        for(Map.Entry<ScreenKey,Near> entry:near.entrySet())
            ShareWatching.wantSound(new ShareWatching.Screen(entry.getKey().owner(),entry.getKey().id()),entry.getValue().anchor());
        for(Iterator<Map.Entry<AudioKey,Listening>> it=LISTENING.entrySet().iterator();it.hasNext();) {
            Listening l=it.next().getValue();
            Near found=near.get(new ScreenKey(l.owner,l.screen));
            if(found==null) {l.close(mc);it.remove();}
            else {l.near=found;l.update(mc,now);}
        }
    }

    private static Map<ScreenKey,Near> scan(Minecraft mc,ClientPacketListener connection) {
        Map<ScreenKey,Near> result=new HashMap<>();
        UUID me=mc.player.getUUID();
        Vec3 ear=mc.gameRenderer.getMainCamera().position();
        double reach=KEEP+2;
        Set<ScreenGroups.Group> seen=new HashSet<>();
        for(Iterator<ScreenBlockEntity> it=ScreenBlockEntity.clientLoaded().iterator();it.hasNext();) {
            ScreenBlockEntity screen=it.next();
            if(screen.getLevel()!=mc.level || screen.isRemoved()) {it.remove();continue;}
            UUID owner=screen.owner();
            if(owner==null || owner.equals(me) || connection.getPlayerInfo(owner)==null)continue;
            if(screen.getBlockPos().distToCenterSqr(ear)>reach*reach)continue;
            ScreenGroups.Group group=ScreenGroups.of(mc.level,screen.getBlockPos());
            if(group==null || !seen.add(group) || !group.sharedWith(mc.level,me))continue;
            if(WatchChoices.muted(mc.level,group)||WatchChoices.hidden(mc.level,group))continue;
            Vec3 point=group.nearestPoint(ear);
            double distance=point.distanceTo(ear);
            if(distance<=KEEP) {
                UUID id=ShareStream.idOf(group.screenId(mc.level));
                result.put(new ScreenKey(owner,id),new Near(group.anchor(),id,point,distance));
            }
        }
        TabletChannels.Channel held=TabletChannels.held(mc);
        if(held!=null && !held.owner().equals(me) && connection.getPlayerInfo(held.owner())!=null)
            result.put(new ScreenKey(held.owner(),held.id()),new Near(held.pos(),held.id(),ear,0));
        return result;
    }

    private static float volumeAt(double distance) {
        if(distance<=FULL)return 1;
        return (float)Math.max(0,1-(distance-FULL)/(RANGE-FULL));
    }

"""
s=s[:start]+replacement+s[end:]
s=s.replace("static final double RANGE = 24, FULL = 3;","static final double RANGE = 10, FULL = 3;")
s=s.replace("private static void startPump() {","private static synchronized void startPump() {")
s=s.replace("        Near near;\n","        volatile Near near;\n")
put(p,s)

# The tablet can watch a remote host screen without walking to the 128-block radius.
# The owner must still be host, broadcast must be enabled, and the guest must hold the tablet.
p="src/main/java/com/desktopscreens/ShareRelay.java"
rep(p,"        if (watcher.distanceToSqr(Vec3.atCenterOf(pos)) > RANGE * RANGE) return;",
"""        if (watcher.distanceToSqr(Vec3.atCenterOf(pos)) > RANGE * RANGE
             && !(HostBroadcast.isEnabled(Players.server(watcher))
             && owner.equals(HostBroadcast.owner(Players.server(watcher))) && hasTablet(watcher)))return;""")
rep(p,"if (player.level().dimension() != i.dimension || player.distanceToSqr(Vec3.atCenterOf(i.pos)) > RANGE * RANGE) return false;",
"""if(player.level().dimension()!=i.dimension)return false;
        if(player.distanceToSqr(Vec3.atCenterOf(i.pos))>RANGE*RANGE
            && !(HostBroadcast.isEnabled(Players.server(player))
            && owner.equals(HostBroadcast.owner(Players.server(player))) && hasTablet(player)))return false;""")
rep(p,"    private static boolean stillWatching(",
"""    private static boolean hasTablet(ServerPlayer player) {
        return player.getMainHandItem().getItem() instanceof TabletItem
            || player.getOffhandItem().getItem() instanceof TabletItem;
    }

    private static boolean stillWatching(""")

# Only the integrated world's owner can switch the TVs on/off while broadcasting.
p="src/main/java/com/desktopscreens/ScreenBlock.java"
rep(p,"""        if (level.isClientSide()) return InteractionResult.SUCCESS;
        if (!(level.getBlockEntity(pos) instanceof ScreenBlockEntity clicked)) return InteractionResult.PASS;""",
"""        if (level.isClientSide()) return InteractionResult.SUCCESS;
        if(level.getServer()!=null && HostBroadcast.isEnabled(level.getServer())
            && !player.getUUID().equals(HostBroadcast.owner(level.getServer()))) {
            Players.overlay(player,Component.literal("Seul l'hote peut gerer les ecrans."));
            return InteractionResult.CONSUME;
        }
        if (!(level.getBlockEntity(pos) instanceof ScreenBlockEntity clicked)) return InteractionResult.PASS;""")

# A physical screen's picture can also be read on the tablet.
p="src/main/java/com/desktopscreens/client/SharedPictures.java"
rep(p,"    /** Marks {@code s} as wanted and puts up its newest picture that's due. */",
"""    static WorldScreens.Picture channel(Minecraft mc,UUID owner,UUID id,net.minecraft.core.BlockPos pos) {
        ShareWatching.Screen screen=new ShareWatching.Screen(owner,id);
        ShareWatching.wantPictures(screen,pos);
        Shown shown=SHOWN.get(screen);
        if(shown==null)return null;
        long now=System.nanoTime();
        Shared current=show(STREAMS.get(shown.current),now);
        if(current==null || current.width==0) {
            Shared before=shown.previous==null?null:show(STREAMS.get(shown.previous),now);
            if(before!=null && before.width>0)current=before;
        }
        return current==null || current.width==0?null
            :new WorldScreens.Picture(current.renderType,current.texture,current.width,current.height,
                0,0,current.width,current.height,null);
    }

    /** Marks {@code s} as wanted and puts up its newest picture that's due. */""")
print("V4 patch stage 1: per-window TVs, program audio streams, 10-block radius, guest controls")
