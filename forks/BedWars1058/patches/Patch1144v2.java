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
 * Issue #1144 fix, branch free.
 *
 * AbstractVerImplCmn1#getShopUpgradeIdentifier(ItemStack) currently returns
 * getTag(itemStack, PLUGIN_TAG_TIER_KEY), which is a Java null for items without a tier tag.
 * The old NMS implementations returned the text "null" instead. Appending
 * String.valueOf(Object) keeps that contract without introducing any new branch
 * (so no new stack map frames are required):
 *
 *   return String.valueOf(getTag(itemStack, PLUGIN_TAG_TIER_KEY));
 *
 * args: <in.jar> <out.jar>
 */
public final class Patch1144v2 {

    private static final String TARGET_CLASS = "com/andrei1058/mc/bedwars/AbstractVerImplCmn1";
    private static final String TARGET_METHOD = "getShopUpgradeIdentifier";
    private static final String TARGET_DESC = "(Lorg/bukkit/inventory/ItemStack;)Ljava/lang/String;";

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
                if (entry.getName().equals(TARGET_CLASS + ".class")) {
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
        if (!patched) throw new IllegalStateException("target class not found");
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    private static byte[] patch(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        if (!TARGET_CLASS.equals(cn.name)) throw new IllegalStateException("unexpected class " + cn.name);

        int hits = 0;
        for (MethodNode m : cn.methods) {
            if (!TARGET_METHOD.equals(m.name) || !TARGET_DESC.equals(m.desc)) continue;
            AbstractInsnNode last = m.instructions.getLast();
            while (last != null && last.getOpcode() < 0) last = last.getPrevious();
            if (last == null || last.getOpcode() != Opcodes.ARETURN) {
                throw new IllegalStateException("unexpected method body");
            }
            // stack at this point: [String]; wrap with String.valueOf(Object)
            m.instructions.insertBefore(last, new MethodInsnNode(Opcodes.INVOKESTATIC, "java/lang/String",
                    "valueOf", "(Ljava/lang/Object;)Ljava/lang/String;", false));
            hits++;
        }
        if (hits != 1) throw new IllegalStateException("patched " + hits + " methods");

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
