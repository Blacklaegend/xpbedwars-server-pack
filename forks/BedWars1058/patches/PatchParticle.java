import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.tree.*;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/**
 * Replace AbstractVerImplCmn1#playRedStoneDot with a pure-Bukkit implementation.
 * args: <in.jar> <out.jar> <ParticleFix.class>
 */
public final class PatchParticle {

    private static final String TARGET = "com/andrei1058/mc/bedwars/AbstractVerImplCmn1";
    private static final String HELPER = "com/andrei1058/bedwars/support/version/ParticleFix";

    public static void main(String[] args) throws Exception {
        File src = new File(args[0]);
        File dst = new File(args[1]);
        byte[] helper = Files.readAllBytes(new File(args[2]).toPath());
        boolean patched = false;

        try (ZipFile zin = new ZipFile(src);
             ZipOutputStream zout = new ZipOutputStream(new FileOutputStream(dst))) {
            Enumeration<? extends ZipEntry> en = zin.entries();
            while (en.hasMoreElements()) {
                ZipEntry entry = en.nextElement();
                byte[] data = readAll(zin.getInputStream(entry));
                if (entry.getName().equals(TARGET + ".class")) {
                    data = patch(data);
                    patched = true;
                }
                ZipEntry copy = new ZipEntry(entry.getName());
                copy.setTime(entry.getTime());
                zout.putNextEntry(copy);
                zout.write(data);
                zout.closeEntry();
            }
            ZipEntry he = new ZipEntry(HELPER + ".class");
            zout.putNextEntry(he);
            zout.write(helper);
            zout.closeEntry();
        }
        if (!patched) throw new IllegalStateException("target not found");
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    private static byte[] patch(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        MethodNode m = null;
        for (MethodNode method : cn.methods) {
            if ("playRedStoneDot".equals(method.name) && "(Lorg/bukkit/entity/Player;)V".equals(method.desc)) {
                m = method;
                break;
            }
        }
        if (m == null) throw new IllegalStateException("playRedStoneDot not found");

        InsnList list = new InsnList();
        list.add(new VarInsnNode(Opcodes.ALOAD, 1));
        list.add(new MethodInsnNode(Opcodes.INVOKESTATIC, HELPER, "playRedstone",
                "(Lorg/bukkit/entity/Player;)V", false));
        list.add(new InsnNode(Opcodes.RETURN));
        m.instructions = list;
        m.tryCatchBlocks = new java.util.ArrayList<>();
        m.localVariables = null;

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
