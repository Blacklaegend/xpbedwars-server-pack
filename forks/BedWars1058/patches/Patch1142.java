import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.commons.ClassRemapper;
import org.objectweb.asm.commons.SimpleRemapper;
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
 * Bytecode patcher for BedWars1058 25.5-SNAPSHOT.
 *
 * Fixes (issue #1142):
 *  1. despawnable classes (silverfish / iron golem) reference the removed versioned CraftBukkit package
 *     "org.bukkit.craftbukkit.v1_21_R1" which no longer exists on Paper 1.20.5+ => NoClassDefFoundError
 *     on spawn, which in turn breaks name, despawn task and targeting of the entity.
 *     Remapped to the unversioned "org.bukkit.craftbukkit" package.
 *  2. remove PathfinderGoalHurtByTarget from the despawnables so they do not turn on their owner/team.
 *  3. Armor purchase weight gate: never block armor purchases based on the cached category weight,
 *     so losing non permanent armor cannot soft lock the shop (CategoryContent#execute).
 *
 * args: <in.jar> <out.jar>
 */
public final class Patch1142 {

    private static final String CB_OLD = "org/bukkit/craftbukkit/v1_21_R1/";
    private static final String CB_NEW = "org/bukkit/craftbukkit/";

    private static final Set<String> DESPAWNABLE_CLASSES = new HashSet<>(Arrays.asList(
            "com/andrei1058/mc/bedwars/despawnable/AbstractDespawnableProvider",
            "com/andrei1058/mc/bedwars/despawnable/TeamSilverfish",
            "com/andrei1058/mc/bedwars/despawnable/TeamIronGolem"));

    private static final String CATEGORY_CONTENT = "com/andrei1058/bedwars/shop/main/CategoryContent";
    private static final String HELPER_NAME = "bw1142IsArmorCategory";
    private static final String HELPER_DESC = "(Lcom/andrei1058/bedwars/shop/main/ShopCategory;)Z";

    public static void main(String[] args) throws Exception {
        File src = new File(args[0]);
        File dst = new File(args[1]);

        int despawnables = 0;
        int goalsRemoved = 0;
        int armorPatched = 0;

        try (ZipFile zin = new ZipFile(src);
             ZipOutputStream zout = new ZipOutputStream(new FileOutputStream(dst))) {
            Enumeration<? extends ZipEntry> en = zin.entries();
            while (en.hasMoreElements()) {
                ZipEntry entry = en.nextElement();
                byte[] data = readAll(zin.getInputStream(entry));
                String name = entry.getName();

                if (name.endsWith(".class")) {
                    String className = name.substring(0, name.length() - ".class".length());
                    if (DESPAWNABLE_CLASSES.contains(className)) {
                        data = remapCraftBukkit(data);
                        data = removeHurtByTarget(data, className);
                        despawnables++;
                    } else if (CATEGORY_CONTENT.equals(className)) {
                        data = patchArmorWeight(data);
                        armorPatched++;
                    }
                }

                ZipEntry copy = new ZipEntry(name);
                copy.setTime(entry.getTime());
                zout.putNextEntry(copy);
                zout.write(data);
                zout.closeEntry();
            }
        }

        System.out.println("despawnable classes patched: " + despawnables);
        System.out.println("CategoryContent patched: " + armorPatched);
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    /** Rewrite the removed versioned CraftBukkit package to the unversioned one. */
    private static byte[] remapCraftBukkit(byte[] data) {
        Map<String, String> mapping = new HashMap<>();
        mapping.put(CB_OLD + "entity/CraftEntity", CB_NEW + "entity/CraftEntity");
        mapping.put(CB_OLD + "entity/CraftHumanEntity", CB_NEW + "entity/CraftHumanEntity");
        mapping.put(CB_OLD + "attribute/CraftAttributeMap", CB_NEW + "attribute/CraftAttributeMap");
        ClassReader cr = new ClassReader(data);
        ClassWriter cw = new ClassWriter(0);
        cr.accept(new ClassRemapper(cw, new SimpleRemapper(mapping)), 0);
        return cw.toByteArray();
    }

    /**
     * Drop "targetSelector.a(1, new PathfinderGoalHurtByTarget(entity))" from spawn().
     * The remaining nearest-attackable-target goal already filters by team.
     */
    private static byte[] removeHurtByTarget(byte[] data, String className) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);

        int removed = 0;
        for (MethodNode m : cn.methods) {
            if (!"spawn".equals(m.name)) continue;
            AbstractInsnNode[] insns = m.instructions.toArray();
            for (int i = 0; i < insns.length; i++) {
                AbstractInsnNode n = insns[i];
                if (!(n instanceof TypeInsnNode)) continue;
                TypeInsnNode t = (TypeInsnNode) n;
                if (t.getOpcode() != Opcodes.NEW || !"net/minecraft/world/entity/ai/goal/target/PathfinderGoalHurtByTarget".equals(t.desc)) {
                    continue;
                }
                // expected sequence: [aload targetSelector] iconst_1 [aload entity] new PathfinderGoalHurtByTarget dup aload entity invokespecial <init>(EntityInsentient)V invokevirtual a(IL PathfinderGoal;)V
                AbstractInsnNode start = t;
                for (int back = 0; back < 3 && start.getPrevious() != null; back++) {
                    start = start.getPrevious();
                }
                AbstractInsnNode end = t;
                // find the "a(int, PathfinderGoal)" call after the NEW
                for (int fwd = 0; fwd < 12 && end != null; fwd++) {
                    end = end.getNext();
                    if (end instanceof MethodInsnNode) {
                        MethodInsnNode mi = (MethodInsnNode) end;
                        if ("a".equals(mi.name) && "(ILnet/minecraft/world/entity/ai/goal/PathfinderGoal;)V".equals(mi.desc)) {
                            break;
                        }
                    }
                }
                if (end == null) {
                    throw new IllegalStateException("could not locate goal registration in " + className);
                }
                AbstractInsnNode cursor = start;
                while (true) {
                    AbstractInsnNode next = cursor.getNext();
                    m.instructions.remove(cursor);
                    if (cursor == end) break;
                    cursor = next;
                }
                removed++;
                System.out.println("  removed HurtByTarget goal from " + className + "#spawn");
            }
        }
        if (removed == 0) {
            System.out.println("  WARN: no HurtByTarget goal found in " + className + "#spawn");
        }
        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        cn.accept(cw);
        return cw.toByteArray();
    }

    /**
     * In CategoryContent#execute, skip the category weight gate for armor categories:
     *
     * if (!isArmorCategory(father)) {
     *     if (shopCache.getCategoryWeight(father) > weight) return;
     * }
     */
    private static byte[] patchArmorWeight(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        if (!CATEGORY_CONTENT.equals(cn.name)) {
            throw new IllegalStateException("unexpected class " + cn.name);
        }

        MethodNode execute = null;
        for (MethodNode m : cn.methods) {
            if ("execute".equals(m.name)
                    && "(Lorg/bukkit/entity/Player;Lcom/andrei1058/bedwars/shop/ShopCache;I)V".equals(m.desc)) {
                execute = m;
                break;
            }
        }
        if (execute == null) {
            throw new IllegalStateException("CategoryContent#execute not found");
        }

        // locate the gate: aload_3? no: this.getField father -> getstatic CategoryContent.father
        AbstractInsnNode gateStart = null;
        for (AbstractInsnNode n = execute.instructions.getFirst(); n != null; n = n.getNext()) {
            if (n instanceof FieldInsnNode) {
                FieldInsnNode f = (FieldInsnNode) n;
                if (f.getOpcode() == Opcodes.GETFIELD && "father".equals(f.name)
                        && "Lcom/andrei1058/bedwars/shop/main/ShopCategory;".equals(f.desc)) {
                    gateStart = n;
                    break;
                }
            }
        }
        if (gateStart == null) {
            throw new IllegalStateException("weight gate not found");
        }

        // gateEnd = first RETURN after gateStart
        AbstractInsnNode gateEnd = gateStart;
        while (gateEnd != null && gateEnd.getOpcode() != Opcodes.RETURN) {
            gateEnd = gateEnd.getNext();
        }
        if (gateEnd == null) {
            throw new IllegalStateException("weight gate return not found");
        }

        int slot = execute.maxLocals;
        execute.maxLocals += 1;

        LabelNode endLabel = new LabelNode();
        InsnList pre = new InsnList();
        // slot = this.bw1142IsArmorCategory(this.father)
        pre.add(new VarInsnNode(Opcodes.ALOAD, 0));
        pre.add(new FieldInsnNode(Opcodes.GETFIELD, CATEGORY_CONTENT, "father",
                "Lcom/andrei1058/bedwars/shop/main/ShopCategory;"));
        pre.add(new MethodInsnNode(Opcodes.INVOKESTATIC, CATEGORY_CONTENT, HELPER_NAME, HELPER_DESC, false));
        pre.add(new VarInsnNode(Opcodes.ISTORE, slot));
        // if (slot == 0) go run the original gate, else jump after it
        pre.add(new VarInsnNode(Opcodes.ILOAD, slot));
        pre.add(new JumpInsnNode(Opcodes.IFNE, endLabel));
        execute.instructions.insert(pre);

        execute.instructions.insert(gateEnd, endLabel);

        cn.methods.add(buildArmorHelper());
        System.out.println("  patched armor weight gate in CategoryContent#execute");

        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS);
        cn.accept(cw);
        return cw.toByteArray();
    }

    /** private static boolean bw1142IsArmorCategory(ShopCategory category) { ... } */
    private static MethodNode buildArmorHelper() {
        MethodNode m = new MethodNode(Opcodes.ACC_PRIVATE | Opcodes.ACC_STATIC | Opcodes.ACC_SYNTHETIC,
                HELPER_NAME, HELPER_DESC, null, null);
        LabelNode notArmor = new LabelNode();
        LabelNode end = new LabelNode();
        InsnList l = m.instructions;
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new JumpInsnNode(Opcodes.IFNULL, notArmor));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "com/andrei1058/bedwars/shop/main/ShopCategory",
                "getName", "()Ljava/lang/String;", false));
        l.add(new LdcInsnNode("armor"));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/lang/String",
                "equalsIgnoreCase", "(Ljava/lang/String;)Z", false));
        l.add(new JumpInsnNode(Opcodes.IFEQ, notArmor));
        l.add(new InsnNode(Opcodes.ICONST_1));
        l.add(new JumpInsnNode(Opcodes.GOTO, end));
        l.add(notArmor);
        l.add(new InsnNode(Opcodes.ICONST_0));
        l.add(end);
        l.add(new InsnNode(Opcodes.IRETURN));
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
