import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.*;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/**
 * Armor rule v3:
 *  - CategoryContent.execute: always apply the weight gate (same tier and lower are blocked).
 *    The "lost armor" exception is disabled; instead the shop weight map is cleared on respawn,
 *    which is the actual "reset after death" behaviour.
 *  - ShopCache.managePermanentsAndDowngradables: clear categoryWeight at the start.
 *
 * args: <in.jar> <out.jar>
 */
public final class PatchArmorReset {

    private static final String CC = "com/andrei1058/bedwars/shop/main/CategoryContent";
    private static final String SC = "com/andrei1058/bedwars/shop/ShopCache";
    private static final String EXEC_DESC = "(Lorg/bukkit/entity/Player;Lcom/andrei1058/bedwars/shop/ShopCache;I)V";
    private static final String RESPAWN_DESC = "(Lcom/andrei1058/bedwars/arena/Arena;)V";

    public static void main(String[] args) throws Exception {
        File src = new File(args[0]);
        File dst = new File(args[1]);
        boolean patchedCc = false;
        boolean patchedSc = false;

        try (ZipFile zin = new ZipFile(src);
             ZipOutputStream zout = new ZipOutputStream(new FileOutputStream(dst))) {
            Enumeration<? extends ZipEntry> en = zin.entries();
            while (en.hasMoreElements()) {
                ZipEntry entry = en.nextElement();
                byte[] data = readAll(zin.getInputStream(entry));
                if (entry.getName().equals(CC + ".class")) {
                    data = patchCategoryContent(data);
                    patchedCc = true;
                } else if (entry.getName().equals(SC + ".class")) {
                    data = patchShopCache(data);
                    patchedSc = true;
                }
                ZipEntry copy = new ZipEntry(entry.getName());
                copy.setTime(entry.getTime());
                zout.putNextEntry(copy);
                zout.write(data);
                zout.closeEntry();
            }
        }
        if (!patchedCc || !patchedSc) throw new IllegalStateException("classes not found");
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    private static byte[] patchCategoryContent(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        MethodNode exec = null;
        for (MethodNode m : cn.methods) {
            if ("execute".equals(m.name) && EXEC_DESC.equals(m.desc)) {
                exec = m;
                break;
            }
        }
        if (exec == null) throw new IllegalStateException("execute not found");

        int replaced = 0;
        for (AbstractInsnNode n = exec.instructions.getFirst(); n != null; n = n.getNext()) {
            if (n instanceof MethodInsnNode) {
                MethodInsnNode mi = (MethodInsnNode) n;
                if ("bw1142HasLostArmor".equals(mi.name) && CC.equals(mi.owner)) {
                    // keep the call (it consumes its arguments), discard the result and force false
                    AbstractInsnNode next = n.getNext();
                    if (next instanceof VarInsnNode && next.getOpcode() == Opcodes.ISTORE) {
                        int slot = ((VarInsnNode) next).var;
                        InsnList list = new InsnList();
                        list.add(new InsnNode(Opcodes.POP));
                        list.add(new InsnNode(Opcodes.ICONST_0));
                        list.add(new VarInsnNode(Opcodes.ISTORE, slot));
                        exec.instructions.insert(next, list);
                        exec.instructions.remove(next);
                        replaced++;
                    }
                }
            }
        }
        if (replaced != 1) throw new IllegalStateException("expected 1 hasLostArmor call, got " + replaced);

        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        cn.accept(cw);
        return cw.toByteArray();
    }

    private static byte[] patchShopCache(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        MethodNode method = null;
        for (MethodNode m : cn.methods) {
            if ("managePermanentsAndDowngradables".equals(m.name) && RESPAWN_DESC.equals(m.desc)) {
                method = m;
                break;
            }
        }
        if (method == null) throw new IllegalStateException("respawn method not found");
        // avoid double patching
        for (AbstractInsnNode n = method.instructions.getFirst(); n != null; n = n.getNext()) {
            if (n instanceof MethodInsnNode) {
                MethodInsnNode mi = (MethodInsnNode) n;
                if ("java/util/HashMap".equals(mi.owner) && "clear".equals(mi.name)) return data;
            }
        }
        InsnList pre = new InsnList();
        pre.add(new VarInsnNode(Opcodes.ALOAD, 0));
        pre.add(new FieldInsnNode(Opcodes.GETFIELD, SC, "categoryWeight", "Ljava/util/HashMap;"));
        pre.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/util/HashMap", "clear", "()V", false));
        method.instructions.insert(pre);

        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        cn.accept(cw);
        return cw.toByteArray();
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
