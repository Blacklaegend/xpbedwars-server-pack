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
 * Rewrites one class inside a plugin jar:
 * AbstractVerImplCmn1#getShopUpgradeIdentifier(ItemStack) is made null-safe by routing the
 * raw tag lookup through a new small static helper that maps Java null to the "null" sentinel.
 */
public class JarPatcher {

    private static final String TARGET_CLASS = "com/andrei1058/mc/bedwars/AbstractVerImplCmn1";
    private static final String TARGET_METHOD = "getShopUpgradeIdentifier";
    private static final String TARGET_DESC = "(Lorg/bukkit/inventory/ItemStack;)Ljava/lang/String;";
    private static final String HELPER = "bw1144ToShopIdentifier";
    private static final String HELPER_DESC = "(Ljava/lang/String;)Ljava/lang/String;";

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
                    byte[] rewritten = patch(data);
                    System.out.println("patched " + entry.getName() + ": " + data.length + " -> " + rewritten.length + " bytes");
                    data = rewritten;
                    patched = true;
                }
                ZipEntry copy = new ZipEntry(entry.getName());
                copy.setTime(entry.getTime());
                zout.putNextEntry(copy);
                zout.write(data);
                zout.closeEntry();
            }
        }
        if (!patched) {
            throw new IllegalStateException("target class not found in " + src);
        }
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    private static byte[] patch(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        if (!TARGET_CLASS.equals(cn.name)) {
            throw new IllegalStateException("unexpected class " + cn.name);
        }

        int hits = 0;
        for (MethodNode m : cn.methods) {
            if (!TARGET_METHOD.equals(m.name) || !TARGET_DESC.equals(m.desc)) continue;
            InsnList insns = m.instructions;
            AbstractInsnNode last = insns.getLast();
            while (last != null && last.getOpcode() < 0) {
                last = last.getPrevious();
            }
            if (last == null || last.getOpcode() != Opcodes.ARETURN) {
                throw new IllegalStateException("unexpected method body in " + TARGET_METHOD
                        + ", last=" + (last == null ? "null" : last.getClass().getSimpleName() + "/" + last.getOpcode()));
            }
            insns.insertBefore(last, new MethodInsnNode(Opcodes.INVOKESTATIC, TARGET_CLASS, HELPER, HELPER_DESC, false));
            hits++;
        }
        if (hits != 1) {
            throw new IllegalStateException("patched " + hits + " methods");
        }

        cn.methods.add(buildHelper());

        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        cn.accept(cw);
        return cw.toByteArray();
    }

    /** private static String bw1144ToShopIdentifier(String s) { return s == null ? "null" : s; } */
    private static MethodNode buildHelper() {
        MethodNode m = new MethodNode(
                Opcodes.ACC_PRIVATE | Opcodes.ACC_STATIC | Opcodes.ACC_SYNTHETIC,
                HELPER, HELPER_DESC, null, null);
        LabelNode nonNull = new LabelNode();
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        m.instructions.add(new JumpInsnNode(Opcodes.IFNONNULL, nonNull));
        m.instructions.add(new LdcInsnNode("null"));
        m.instructions.add(new InsnNode(Opcodes.ARETURN));
        m.instructions.add(nonNull);
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        m.instructions.add(new InsnNode(Opcodes.ARETURN));
        return m;
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
