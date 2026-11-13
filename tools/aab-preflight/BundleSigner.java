import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;
import java.security.CodeSigner;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Locale;
import java.util.jar.JarFile;

class BundleSigner {
    public static void main(String[] args) throws Exception {
        try (var bundle = new JarFile(Path.of(args[0]).toFile(), true)) {
            String fingerprint = null;
            var entries = bundle.entries();
            while (entries.hasMoreElements()) {
                var entry = entries.nextElement();
                if (entry.isDirectory() || isSignatureMetadata(entry.getName())) {
                    continue;
                }

                try (InputStream data = bundle.getInputStream(entry)) {
                    // JarFile verifies an entry's digest only after it has been read.
                    data.transferTo(java.io.OutputStream.nullOutputStream());
                }
                CodeSigner[] signers = entry.getCodeSigners();
                if (signers == null || signers.length != 1) {
                    throw new IOException("Every bundle entry must have exactly one signer.");
                }
                var certificate = signers[0].getSignerCertPath().getCertificates().get(0);
                String current = HexFormat.of().formatHex(
                        MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded()));
                if (fingerprint != null && !fingerprint.equals(current)) {
                    throw new IOException("Bundle entries use different signing certificates.");
                }
                fingerprint = current;
            }
            if (fingerprint == null) {
                throw new IOException("No signed bundle entries found.");
            }
            System.out.println(fingerprint);
        } catch (IOException | SecurityException error) {
            System.err.println(error.getMessage());
            System.exit(1);
        }
    }

    private static boolean isSignatureMetadata(String name) {
        String upper = name.toUpperCase(Locale.ROOT);
        if (!upper.startsWith("META-INF/")) {
            return false;
        }
        String file = upper.substring("META-INF/".length());
        return !file.contains("/") && (file.equals("MANIFEST.MF") || file.endsWith(".SF")
                || file.endsWith(".RSA") || file.endsWith(".DSA") || file.endsWith(".EC")
                || file.startsWith("SIG-"));
    }
}
