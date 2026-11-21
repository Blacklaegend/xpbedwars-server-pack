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
 * BedWars1058 25.5-SNAPSHOT bytecode patcher for issue #1142.
 *
 * The 1.21 despawnable code was compiled against the versioned CraftBukkit package
 * org.bukkit.craftbukkit.v1_21_R1 and Spigot-mapped NMS fields (EntityInsentient.bW/bX,
 * craftAttributes). Paper 1.21.4 no longer has either, so every BedBug / IronGolem spawn throws
 * NoClassDefFoundError and the entity is never registered (no name, no despawn, no targeting).
 *
 * Rewrites the despawnable entry points with Bukkit-only code and drops the armor category
 * weight gate so lost armor cannot soft lock the shop.
 *
 * args: <in.jar> <out.jar>
 */
public final class Patch1142b {

    private static final String ADP = "com/andrei1058/mc/bedwars/despawnable/AbstractDespawnableProvider";
    private static final String TS = "com/andrei1058/mc/bedwars/despawnable/TeamSilverfish";
    private static final String TIG = "com/andrei1058/mc/bedwars/despawnable/TeamIronGolem";
    private static final String DA = "com/andrei1058/mc/bedwars/despawnable/DespawnableAttributes";

    private static final String CC = "com/andrei1058/bedwars/shop/main/CategoryContent";
    private static final String HELPER = "bw1142IsArmorCategory";
    private static final String HELPER_DESC = "(Lcom/andrei1058/bedwars/shop/main/ShopCategory;)Z";

    private static final String LIVING = "org/bukkit/entity/LivingEntity";
    private static final String AI = "org/bukkit/attribute/AttributeInstance";
    private static final String ATTR = "org/bukkit/attribute/Attribute";

    public static void main(String[] args) throws Exception {
        File src = new File(args[0]);
        File dst = new File(args[1]);

        int patched = 0;
        try (ZipFile zin = new ZipFile(src);
             ZipOutputStream zout = new ZipOutputStream(new FileOutputStream(dst))) {
            Enumeration<? extends ZipEntry> en = zin.entries();
            while (en.hasMoreElements()) {
                ZipEntry entry = en.nextElement();
                byte[] data = readAll(zin.getInputStream(entry));
                String name = entry.getName();
                if (name.endsWith(".class")) {
                    String cn = name.substring(0, name.length() - 6);
                    switch (cn) {
                        case ADP:
                            data = patchAbstract(data);
                            patched++;
                            break;
                        case TS:
                            data = patchSpawn(data, TS, "org/bukkit/entity/Silverfish");
                            patched++;
                            break;
                        case TIG:
                            data = patchSpawn(data, TIG, "org/bukkit/entity/IronGolem");
                            patched++;
                            break;
                        case CC:
                            data = patchArmorWeight(data);
                            patched++;
                            break;
                        default:
                            break;
                    }
                }
                ZipEntry copy = new ZipEntry(name);
                copy.setTime(entry.getTime());
                zout.putNextEntry(copy);
                zout.write(data);
                zout.closeEntry();
            }
        }
        System.out.println("patched classes: " + patched);
        System.out.println("wrote " + dst + " (" + dst.length() + " bytes)");
    }

    // ------------------------------------------------------------------ AbstractDespawnableProvider

    private static byte[] patchAbstract(byte[] data) {
        ClassNode cn = read(data);

        MethodNode clear = method(cn, "clearSelectors", "(Lnet/minecraft/world/entity/EntityCreature;)V");
        reset(clear);
        clear.instructions.add(new InsnNode(Opcodes.RETURN));

        MethodNode apply = method(cn, "applyDefaultSettings",
                "(Lorg/bukkit/entity/LivingEntity;Lcom/andrei1058/mc/bedwars/despawnable/DespawnableAttributes;" +
                        "Lcom/andrei1058/bedwars/api/arena/team/ITeam;)V");
        reset(apply);
        InsnList l = apply.instructions;

        // entity.setRemoveWhenFarAway(false); entity.setPersistent(true); entity.setCustomNameVisible(true);
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new InsnNode(Opcodes.ICONST_0));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, LIVING, "setRemoveWhenFarAway", "(Z)V", true));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new InsnNode(Opcodes.ICONST_1));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, LIVING, "setPersistent", "(Z)V", true));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new InsnNode(Opcodes.ICONST_1));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, LIVING, "setCustomNameVisible", "(Z)V", true));
        // entity.setCustomName(this.getDisplayName(attr, team));
        l.add(new VarInsnNode(Opcodes.ALOAD, 1));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new VarInsnNode(Opcodes.ALOAD, 2));
        l.add(new VarInsnNode(Opcodes.ALOAD, 3));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, ADP, "getDisplayName",
                "(Lcom/andrei1058/mc/bedwars/despawnable/DespawnableAttributes;" +
                        "Lcom/andrei1058/bedwars/api/arena/team/ITeam;)Ljava/lang/String;", false));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, LIVING, "setCustomName", "(Ljava/lang/String;)V", true));

        // entity.setMaxHealth(attr.health()) style: attribute instance setBaseValue
        setAttribute(l, "health", "getHealth", "MAX_HEALTH");
        setAttribute(l, "speed", "getSpeed", "MOVEMENT_SPEED");
        setAttribute(l, "damage", "getDamage", "ATTACK_DAMAGE");

        // entity.setHealth(entity.getMaxHealth());
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, LIVING, "getMaxHealth", "()D", true));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, LIVING, "setHealth", "(D)V", true));

        l.add(new InsnNode(Opcodes.RETURN));

        for (String name : new String[]{"getTargetSelector", "getGoalSelector"}) {
            MethodNode m = method(cn, name,
                    "(Lnet/minecraft/world/entity/EntityCreature;)Lnet/minecraft/world/entity/ai/goal/PathfinderGoalSelector;");
            reset(m);
            m.instructions.add(new InsnNode(Opcodes.ACONST_NULL));
            m.instructions.add(new InsnNode(Opcodes.ARETURN));
        }
        MethodNode goal = method(cn, "getTargetGoal",
                "(Lnet/minecraft/world/entity/EntityInsentient;Lcom/andrei1058/bedwars/api/arena/team/ITeam;" +
                        "Lcom/andrei1058/bedwars/api/server/VersionSupport;)Lnet/minecraft/world/entity/ai/goal/PathfinderGoal;");
        reset(goal);
        goal.instructions.add(new InsnNode(Opcodes.ACONST_NULL));
        goal.instructions.add(new InsnNode(Opcodes.ARETURN));
        // notSameTeam(...) is only used by the lambda captured in getTargetGoal; stub it so the
        // class no longer references the removed versioned CraftBukkit classes at all.
        MethodNode notSame = method(cn, "notSameTeam",
                "(Lnet/minecraft/world/entity/Entity;Lcom/andrei1058/bedwars/api/arena/team/ITeam;" +
                        "Lcom/andrei1058/bedwars/api/server/VersionSupport;)Z");
        reset(notSame);
        notSame.instructions.add(new InsnNode(Opcodes.ICONST_0));
        notSame.instructions.add(new InsnNode(Opcodes.IRETURN));

        // the lambda was only referenced from the removed getTargetGoal body
        cn.methods.removeIf(m -> "lambda$getTargetGoal$0".equals(m.name));

        return write(cn);
    }

    /**
     * AttributeInstance ai = entity.getAttribute(Attribute.X);
     * if (ai != null) ai.setBaseValue(attr.getX());
     */
    private static void setAttribute(InsnList l, String recordGetter, String attributeName, String attrConst) {
        LabelNode skip = new LabelNode();
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new FieldInsnNode(Opcodes.GETSTATIC, ATTR, attrConst, "L" + ATTR + ";"));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, LIVING, "getAttribute", "(L" + ATTR + ";)" + "L" + AI + ";", true));
        l.add(new VarInsnNode(Opcodes.ASTORE, 4));
        l.add(new VarInsnNode(Opcodes.ALOAD, 4));
        l.add(new JumpInsnNode(Opcodes.IFNULL, skip));
        l.add(new VarInsnNode(Opcodes.ALOAD, 4));
        l.add(new VarInsnNode(Opcodes.ALOAD, 2));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, DA, recordGetter, "()D", false));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, AI, "setBaseValue", "(D)V", false));
        l.add(skip);
    }

    // ------------------------------------------------------------------ TeamSilverfish / TeamIronGolem

    private static byte[] patchSpawn(byte[] data, String className, String entityType) {
        ClassNode cn = read(data);
        MethodNode m = method(cn, "spawn",
                "(Lcom/andrei1058/mc/bedwars/despawnable/DespawnableAttributes;Lorg/bukkit/Location;" +
                        "Lcom/andrei1058/bedwars/api/arena/team/ITeam;Lcom/andrei1058/bedwars/api/server/VersionSupport;)" +
                        "L" + entityType + ";");
        reset(m);
        InsnList l = m.instructions;
        LabelNode ok = new LabelNode();

        // World world = Objects.requireNonNull(location.getWorld());
        l.add(new VarInsnNode(Opcodes.ALOAD, 2));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/Location", "getWorld", "()Lorg/bukkit/World;", false));
        l.add(new MethodInsnNode(Opcodes.INVOKESTATIC, "java/util/Objects", "requireNonNull",
                "(Ljava/lang/Object;)Ljava/lang/Object;", false));
        l.add(new TypeInsnNode(Opcodes.CHECKCAST, "org/bukkit/World"));
        // Entity e = world.spawnEntity(location, EntityType.X);
        l.add(new VarInsnNode(Opcodes.ALOAD, 2));
        String entityTypeName = entityType.substring(entityType.lastIndexOf('/') + 1).toUpperCase(Locale.ROOT);
        l.add(new FieldInsnNode(Opcodes.GETSTATIC, "org/bukkit/entity/EntityType", entityTypeName,
                "Lorg/bukkit/entity/EntityType;"));
        l.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/World", "spawnEntity",
                "(Lorg/bukkit/Location;Lorg/bukkit/entity/EntityType;)Lorg/bukkit/entity/Entity;", true));
        l.add(new TypeInsnNode(Opcodes.CHECKCAST, entityType));
        l.add(new InsnNode(Opcodes.DUP));
        l.add(new JumpInsnNode(Opcodes.IFNONNULL, ok));
        l.add(new InsnNode(Opcodes.POP));
        l.add(new InsnNode(Opcodes.ACONST_NULL));
        l.add(new InsnNode(Opcodes.ARETURN));
        l.add(ok);
        // stack: [entity]
        // this.applyDefaultSettings(entity, attr, team); entity stays on the stack for the return value
        l.add(new InsnNode(Opcodes.DUP));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new VarInsnNode(Opcodes.ALOAD, 2));
        l.add(new VarInsnNode(Opcodes.ALOAD, 1));
        l.add(new VarInsnNode(Opcodes.ALOAD, 3));
        l.add(new MethodInsnNode(Opcodes.INVOKESPECIAL, ADP, "applyDefaultSettings",
                "(Lorg/bukkit/entity/LivingEntity;Lcom/andrei1058/mc/bedwars/despawnable/DespawnableAttributes;" +
                        "Lcom/andrei1058/bedwars/api/arena/team/ITeam;)V", false));
        l.add(new InsnNode(Opcodes.ARETURN));

        return write(cn);
    }

    // ------------------------------------------------------------------ armor weight

    private static byte[] patchArmorWeight(byte[] data) {
        ClassNode cn = read(data);
        MethodNode execute = method(cn, "execute",
                "(Lorg/bukkit/entity/Player;Lcom/andrei1058/bedwars/shop/ShopCache;I)V");

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
        if (gateStart == null) throw new IllegalStateException("weight gate not found");

        AbstractInsnNode gateEnd = gateStart;
        while (gateEnd != null && gateEnd.getOpcode() != Opcodes.RETURN) gateEnd = gateEnd.getNext();
        if (gateEnd == null) throw new IllegalStateException("gate return not found");

        int slot = execute.maxLocals;
        execute.maxLocals += 1;
        LabelNode end = new LabelNode();

        InsnList pre = new InsnList();
        pre.add(new VarInsnNode(Opcodes.ALOAD, 0));
        pre.add(new FieldInsnNode(Opcodes.GETFIELD, CC, "father",
                "Lcom/andrei1058/bedwars/shop/main/ShopCategory;"));
        pre.add(new MethodInsnNode(Opcodes.INVOKESTATIC, CC, HELPER, HELPER_DESC, false));
        pre.add(new VarInsnNode(Opcodes.ISTORE, slot));
        pre.add(new VarInsnNode(Opcodes.ILOAD, slot));
        pre.add(new JumpInsnNode(Opcodes.IFNE, end));
        execute.instructions.insert(pre);
        execute.instructions.insert(gateEnd, end);

        cn.methods.add(buildArmorHelper());
        return write(cn);
    }

    private static MethodNode buildArmorHelper() {
        MethodNode m = new MethodNode(Opcodes.ACC_PRIVATE | Opcodes.ACC_STATIC | Opcodes.ACC_SYNTHETIC,
                HELPER, HELPER_DESC, null, null);
        LabelNode notArmor = new LabelNode();
        LabelNode end = new LabelNode();
        InsnList l = m.instructions;
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new JumpInsnNode(Opcodes.IFNULL, notArmor));
        l.add(new VarInsnNode(Opcodes.ALOAD, 0));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "com/andrei1058/bedwars/shop/main/ShopCategory",
                "getName", "()Ljava/lang/String;", false));
        l.add(new LdcInsnNode("armor"));
        l.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/lang/String", "equalsIgnoreCase",
                "(Ljava/lang/String;)Z", false));
        l.add(new JumpInsnNode(Opcodes.IFEQ, notArmor));
        l.add(new InsnNode(Opcodes.ICONST_1));
        l.add(new JumpInsnNode(Opcodes.GOTO, end));
        l.add(notArmor);
        l.add(new InsnNode(Opcodes.ICONST_0));
        l.add(end);
        l.add(new InsnNode(Opcodes.IRETURN));
        return m;
    }

    // ------------------------------------------------------------------ helpers

    private static ClassNode read(byte[] data) {
        ClassNode cn = new ClassNode();
        new ClassReader(data).accept(cn, 0);
        return cn;
    }

    private static byte[] write(ClassNode cn) {
        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS | ClassWriter.COMPUTE_FRAMES);
        cn.accept(cw);
        return cw.toByteArray();
    }

    private static MethodNode method(ClassNode cn, String name, String desc) {
        for (MethodNode m : cn.methods) {
            if (name.equals(m.name) && desc.equals(m.desc)) return m;
        }
        throw new IllegalStateException("method not found: " + cn.name + "#" + name + desc);
    }

    private static void reset(MethodNode m) {
        m.instructions.clear();
        m.tryCatchBlocks = new ArrayList<>();
        m.localVariables = new ArrayList<>();
        m.visibleLocalVariableAnnotations = new ArrayList<>();
        m.invisibleLocalVariableAnnotations = new ArrayList<>();
        m.maxLocals = 8;
        m.maxStack = 8;
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
