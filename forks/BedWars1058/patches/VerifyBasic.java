import org.objectweb.asm.ClassReader;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.MethodNode;
import org.objectweb.asm.tree.analysis.Analyzer;
import org.objectweb.asm.tree.analysis.BasicVerifier;

/**
 * Structural bytecode verification that does not require the referenced classes on the classpath.
 */
public class VerifyBasic {
    public static void main(String[] args) throws Exception {
        int bad = 0;
        for (String file : args) {
            ClassNode cn = new ClassNode();
            new ClassReader(new java.io.FileInputStream(file)).accept(cn, 0);
            for (MethodNode m : cn.methods) {
                if ((m.access & org.objectweb.asm.Opcodes.ACC_ABSTRACT) != 0) continue;
                try {
                    new Analyzer<>(new BasicVerifier()).analyze(cn.name, m);
                } catch (Exception e) {
                    bad++;
                    System.out.println("FAIL " + cn.name + "#" + m.name + m.desc + " -> " + e);
                }
            }
            System.out.println("checked " + cn.name);
        }
        System.out.println(bad == 0 ? "ALL OK" : (bad + " methods failed"));
    }
}
