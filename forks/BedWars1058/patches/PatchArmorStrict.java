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
 * Armor rule: cannot buy the same tier or a lower tier; only upgrades are allowed.
 * The weight gate becomes  categoryWeight >= itemWeight  -> block.
 * (After death the player's armor is gone, the lost-armor check skips the gate and the
 *  next purchase resets the category weight.)
 *
 * args: <in.jar> <out.jar>
 */
public final class PatchArmorStrict {

    private static final String CC = "com/andrei1058/bedwars/shop/main/CategoryContent";
    private static final String EXEC_DESC = "(Lorg/bukkit/entity/Player;Lcom/andrei1058/bedwars/shop/ShopCache;I)V";

    public static void main(String[] args) throws Exception {
        File src = new File(args[0]);
        File dst = new File(args[1]);
        boolean patched = false;

        try (ZipFile zin = new ZipFile(src);
             ZipOutputStream zout = new ZipOutputStream(new FileOutputStream(dst))) {
            Enumeration<? extends ZipEntry> en = zin.entries();
            while (en.hasMoreElements()) {
                ZipEntry entry = en.nextElement();
                byte[] data = readAll(zin.getInputStream(entry));
                if (entry.getName().equals(CC + ".class")) {
                    data = patch(data);
                    patched = true;
                }
                ZipEntry copy = new ZipEntry(entry.getName());
                copy.setTime(entry.getTime());
                zout.putNextEntry(copy);
                zout.write(data);
                zout.closeEntry();
            }
        }
        if (!patched) throw new IllegalStateException("CategoryContent not found");
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    private static byte[] patch(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        MethodNode exec = null;
        for (MethodNode m : cn.methods) {
            if ("execute".equals(m.name) && EXEC_DESC.equals(m.desc)) {
                exec = m;
                break;
            }
        }
        if (exec == null) throw new IllegalStateException("execute method not found");

        int hits = 0;
        for (AbstractInsnNode n = exec.instructions.getFirst(); n != null; n = n.getNext()) {
            if (!(n instanceof MethodInsnNode)) continue;
            MethodInsnNode mi = (MethodInsnNode) n;
            if ("com/andrei1058/bedwars/shop/ShopCache".equals(mi.owner)
                    && "getCategoryWeight".equals(mi.name)) {
                // find the following IF_ICMPLE (categoryWeight > weight) and make it IF_ICMPLT
                AbstractInsnNode p = n.getNext();
                while (p != null) {
                    if (p instanceof JumpInsnNode && p.getOpcode() == Opcodes.IF_ICMPLE) {
                        ((JumpInsnNode) p).setOpcode(Opcodes.IF_ICMPLT);
                        hits++;
                        break;
                    }
                    if (p instanceof MethodInsnNode) break;
                    p = p.getNext();
                }
            }
        }
        if (hits != 1) throw new IllegalStateException("expected 1 weight comparison, found " + hits);

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
