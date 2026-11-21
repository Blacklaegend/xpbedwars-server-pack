import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.*;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.*;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/**
 * 28 HP support.
 *
 * DeathPulse only applies "hp.start" when a player joins for the very first time
 * (PlayerJoinListener checks hasPlayedBefore()), while Bukkit resets the MAX_HEALTH attribute
 * on every login. Returning players therefore always end up at 20 HP.
 * Patch: drop the hasPlayedBefore() guard so the start value is applied on every join.
 *
 * BedWars1058 hard codes setHealth(20.0) in Arena#addPlayer and BedWarsTeam respawn,
 * which leaves a 28 HP player at 20/28 in game.
 * Patch: replace the 20.0 constant with player.getMaxHealth().
 *
 * args: <in.jar> <out.jar> <deathpulse|bedwars>
 */
public final class PatchHealth {

    private static final String DP_LISTENER = "io/github/b4n9z/deathPulse/Listeners/PlayerJoinListener";
    private static final String PLAYER = "org/bukkit/entity/Player";
    private static final String SET_HEALTH = "setHealth";
    private static final String GET_MAX_HEALTH = "getMaxHealth";

    public static void main(String[] args) throws Exception {
        File src = new File(args[0]);
        File dst = new File(args[1]);
        String mode = args[2];

        int touched = 0;
        try (ZipFile zin = new ZipFile(src);
             ZipOutputStream zout = new ZipOutputStream(new FileOutputStream(dst))) {
            Enumeration<? extends ZipEntry> en = zin.entries();
            while (en.hasMoreElements()) {
                ZipEntry entry = en.nextElement();
                byte[] data = readAll(zin.getInputStream(entry));
                String name = entry.getName();

                if (name.endsWith(".class")) {
                    if ("deathpulse".equals(mode) && name.equals(DP_LISTENER + ".class")) {
                        data = patchJoinGuard(data);
                        touched++;
                    } else if ("bedwars".equals(mode) && (
                            name.equals("com/andrei1058/bedwars/arena/Arena.class")
                                    || name.equals("com/andrei1058/bedwars/arena/team/BedWarsTeam.class")
                            || name.equals("com/andrei1058/bedwars/arena/PlayerGoods.class"))) {
                        data = fillToMaxHealth(data);
                        touched++;
                    }
                }

                ZipEntry copy = new ZipEntry(name);
                copy.setTime(entry.getTime());
                zout.putNextEntry(copy);
                zout.write(data);
                zout.closeEntry();
            }
        }
        System.out.println("classes touched: " + touched);
        if (touched == 0) throw new IllegalStateException("nothing patched in " + src);
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    /** if (!player.hasPlayedBefore()) -> always run the block (pop the boolean instead of branching) */
    private static byte[] patchJoinGuard(byte[] data) {
        ClassNode cn = read(data);
        int hits = 0;
        for (MethodNode m : cn.methods) {
            AbstractInsnNode[] insns = m.instructions.toArray();
            for (int i = 0; i < insns.length; i++) {
                AbstractInsnNode n = insns[i];
                if (!(n instanceof MethodInsnNode)) continue;
                MethodInsnNode mi = (MethodInsnNode) n;
                if (!"hasPlayedBefore".equals(mi.name)) continue;
                // next real instruction must be a conditional jump
                AbstractInsnNode next = mi.getNext();
                while (next != null && next.getOpcode() < 0) next = next.getNext();
                if (next instanceof JumpInsnNode && next.getOpcode() == Opcodes.IFNE) {
                    m.instructions.remove(next);
                    m.instructions.insert(mi, new InsnNode(Opcodes.POP));
                    hits++;
                }
            }
        }
        if (hits == 0) throw new IllegalStateException("hasPlayedBefore guard not found");
        System.out.println("  join guard patched: " + hits);
        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS | ClassWriter.COMPUTE_FRAMES);
        cn.accept(cw);
        return cw.toByteArray();
    }

    /** player.setHealth(20.0) -> player.setHealth(player.getMaxHealth()) */
    private static byte[] fillToMaxHealth(byte[] data) {
        ClassNode cn = read(data);
        int hits = 0;
        for (MethodNode m : cn.methods) {
            AbstractInsnNode[] insns = m.instructions.toArray();
            for (int i = 1; i + 1 < insns.length; i++) {
                AbstractInsnNode n = insns[i];
                if (!(n instanceof LdcInsnNode)) continue;
                LdcInsnNode ldc = (LdcInsnNode) n;
                if (!(ldc.cst instanceof Double) || ((Double) ldc.cst) != 20.0d) continue;
                AbstractInsnNode call = insns[i + 1];
                if (!(call instanceof MethodInsnNode)) continue;
                MethodInsnNode mi = (MethodInsnNode) call;
                if (!SET_HEALTH.equals(mi.name) || !PLAYER.equals(mi.owner) || !"(D)V".equals(mi.desc)) continue;

                AbstractInsnNode before = insns[i - 1];
                if (!(before instanceof VarInsnNode) || before.getOpcode() != Opcodes.ALOAD) {
                    throw new IllegalStateException("unexpected receiver before setHealth in " + cn.name);
                }
                int slot = ((VarInsnNode) before).var;

                InsnList replacement = new InsnList();
                replacement.add(new VarInsnNode(Opcodes.ALOAD, slot));
                replacement.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, PLAYER, GET_MAX_HEALTH, "()D", true));
                m.instructions.insertBefore(ldc, replacement);
                m.instructions.remove(ldc);
                hits++;
            }
        }
        if (hits == 0) throw new IllegalStateException("setHealth(20.0) not found in " + cn.name);
        System.out.println("  " + cn.name + ": setHealth(20) -> max health (" + hits + ")");
        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        cn.accept(cw);
        return cw.toByteArray();
    }

    private static ClassNode read(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        return cn;
    }

    private static byte[] readAll(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int r;
        while ((r = in.read(buf)) > 0) out.write(buf, 0, r);
        in.close();
        return out.toByteArray();
    }
}
