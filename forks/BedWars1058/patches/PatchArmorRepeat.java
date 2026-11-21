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
 * Allows re-buying the same (or any lower) armor tier: the armor weight gate is skipped for
 * categories whose name contains "armor".
 *
 * args: <in.jar> <out.jar>
 */
public final class PatchArmorRepeat {

    private static final String CC = "com/andrei1058/bedwars/shop/main/CategoryContent";
    private static final String SC = "com/andrei1058/bedwars/shop/main/ShopCategory";

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

        MethodNode target = null;
        for (MethodNode m : cn.methods) {
            if ("bw1142HasLostArmor".equals(m.name)) {
                target = m;
                break;
            }
        }
        if (target == null) throw new IllegalStateException("armor gate helper not found");

        LabelNode falseLabel = new LabelNode();
        InsnList il = new InsnList();
        il.add(new VarInsnNode(Opcodes.ALOAD, 0));
        il.add(new JumpInsnNode(Opcodes.IFNULL, falseLabel));
        il.add(new VarInsnNode(Opcodes.ALOAD, 0));
        il.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, SC, "getName", "()Ljava/lang/String;", false));
        il.add(new LdcInsnNode("armor"));
        il.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/lang/String", "contains",
                "(Ljava/lang/CharSequence;)Z", false));
        il.add(new JumpInsnNode(Opcodes.IFEQ, falseLabel));
        il.add(new InsnNode(Opcodes.ICONST_1));
        il.add(new InsnNode(Opcodes.IRETURN));
        il.add(falseLabel);
        il.add(new FrameNode(Opcodes.F_SAME, 0, new Object[0], 0, new Object[0]));
        il.add(new InsnNode(Opcodes.ICONST_0));
        il.add(new InsnNode(Opcodes.IRETURN));

        target.instructions.clear();
        target.tryCatchBlocks.clear();
        if (target.localVariables != null) target.localVariables.clear();
        target.instructions.add(il);
        target.maxStack = 2;
        target.maxLocals = 2;

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
