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
 * Upgrades the armor weight handling in CategoryContent#execute:
 * the weight gate is skipped only when the player is not wearing a shop armor tier right now
 * (empty slot or leather). Armor that is kept still blocks a downgrade, lost armor does not
 * soft lock the shop.
 *
 * args: <in.jar> <out.jar>
 */
public final class PatchArmorGate {

    private static final String CC = "com/andrei1058/bedwars/shop/main/CategoryContent";
    private static final String SC = "com/andrei1058/bedwars/shop/main/ShopCategory";
    private static final String HELPER = "bw1142HasLostArmor";
    private static final String HELPER_DESC =
            "(L" + SC + ";Lorg/bukkit/entity/Player;)Z";
    private static final String TIER_HELPER = "bw1142IsNotArmorTier";

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

        MethodNode execute = null;
        for (MethodNode m : cn.methods) {
            if ("execute".equals(m.name)
                    && "(Lorg/bukkit/entity/Player;Lcom/andrei1058/bedwars/shop/ShopCache;I)V".equals(m.desc)) {
                execute = m;
                break;
            }
        }
        if (execute == null) throw new IllegalStateException("execute not found");

        boolean replaced = false;
        for (AbstractInsnNode n = execute.instructions.getFirst(); n != null; n = n.getNext()) {
            if (n instanceof MethodInsnNode) {
                MethodInsnNode mi = (MethodInsnNode) n;
                if ("bw1142IsArmorCategory".equals(mi.name)) {
                    mi.name = HELPER;
                    mi.desc = HELPER_DESC;
                    // stack before call: [father]; now push player (local 1)
                    execute.instructions.insertBefore(mi, new VarInsnNode(Opcodes.ALOAD, 1));
                    replaced = true;
                    break;
                }
            }
        }
        if (!replaced) throw new IllegalStateException("old armor gate helper call not found");

        cn.methods.removeIf(m -> "bw1142IsArmorCategory".equals(m.name));
        cn.methods.add(buildLostArmorHelper());
        cn.methods.add(buildTierHelper());

        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS | ClassWriter.COMPUTE_FRAMES);
        cn.accept(cw);
        return cw.toByteArray();
    }

    private static MethodNode buildLostArmorHelper() {
        MethodNode m = new MethodNode(Opcodes.ACC_PRIVATE | Opcodes.ACC_STATIC | Opcodes.ACC_SYNTHETIC,
                HELPER, HELPER_DESC, null, null);
        InsnList l = m.instructions;
        LabelNode false1 = new LabelNode();

        // category == null || !"armor".equalsIgnoreCase(category.getName()) -> false
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new JumpInsnNode(Opcodes.IFNULL, false1));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, SC, "getName", "()Ljava/lang/String;", false));
        l.add(new LdcInsnNode("armor"));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/lang/String", "equalsIgnoreCase",
                "(Ljava/lang/String;)Z", false));
        l.add(new JumpInsnNode(Opcodes.IFEQ, false1));

        // return isNotArmorTier(boots) || isNotArmorTier(leggings)
        l.add(new VarInsnNode(Opcodes.ALOAD, 1));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/entity/Player", "getInventory",
                "()Lorg/bukkit/inventory/PlayerInventory;", true));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/inventory/PlayerInventory", "getBoots",
                "()Lorg/bukkit/inventory/ItemStack;", false));
        l.add(new MethodInsnNode(Opcodes.INVOKESTATIC, CC, TIER_HELPER,
                "(Lorg/bukkit/inventory/ItemStack;)Z", false));
        LabelNode bootsArmored = new LabelNode();
        l.add(new JumpInsnNode(Opcodes.IFEQ, bootsArmored));
        l.add(new InsnNode(Opcodes.ICONST_1));
        l.add(new InsnNode(Opcodes.IRETURN));
        l.add(bootsArmored);

        l.add(new VarInsnNode(Opcodes.ALOAD, 1));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/entity/Player", "getInventory",
                "()Lorg/bukkit/inventory/PlayerInventory;", true));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/inventory/PlayerInventory", "getLeggings",
                "()Lorg/bukkit/inventory/ItemStack;", false));
        l.add(new MethodInsnNode(Opcodes.INVOKESTATIC, CC, TIER_HELPER,
                "(Lorg/bukkit/inventory/ItemStack;)Z", false));
        l.add(new InsnNode(Opcodes.IRETURN));

        l.add(false1);
        l.add(new InsnNode(Opcodes.ICONST_0));
        l.add(new InsnNode(Opcodes.IRETURN));
        return m;
    }

    /**
     * private static boolean bw1142IsNotArmorTier(ItemStack item) {
     *     if (item == null) return true;
     *     Material type = item.getType();
     *     return type == Material.AIR || type.name().startsWith("LEATHER_");
     * }
     */
    private static MethodNode buildTierHelper() {
        MethodNode t = new MethodNode(Opcodes.ACC_PRIVATE | Opcodes.ACC_STATIC | Opcodes.ACC_SYNTHETIC,
                TIER_HELPER, "(Lorg/bukkit/inventory/ItemStack;)Z", null, null);
        InsnList l = t.instructions;
        LabelNode yes = new LabelNode();
        LabelNode no = new LabelNode();

        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new JumpInsnNode(Opcodes.IFNULL, yes));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/inventory/ItemStack", "getType",
                "()Lorg/bukkit/Material;", false));
        l.add(new VarInsnNode(Opcodes.ASTORE, 1));
        l.add(new VarInsnNode(Opcodes.ALOAD, 1));
        l.add(new FieldInsnNode(Opcodes.GETSTATIC, "org/bukkit/Material", "AIR", "Lorg/bukkit/Material;"));
        l.add(new JumpInsnNode(Opcodes.IF_ACMPEQ, yes));
        l.add(new VarInsnNode(Opcodes.ALOAD, 1));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/Material", "name", "()Ljava/lang/String;", false));
        l.add(new LdcInsnNode("LEATHER_"));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/lang/String", "startsWith",
                "(Ljava/lang/String;)Z", false));
        l.add(new JumpInsnNode(Opcodes.IFNE, yes));
        l.add(new JumpInsnNode(Opcodes.GOTO, no));
        l.add(yes);
        l.add(new InsnNode(Opcodes.ICONST_1));
        l.add(new InsnNode(Opcodes.IRETURN));
        l.add(no);
        l.add(new InsnNode(Opcodes.ICONST_0));
        l.add(new InsnNode(Opcodes.IRETURN));
        return t;
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
