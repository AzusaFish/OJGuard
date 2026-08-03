import java.io.BufferedReader;
import java.io.InputStreamReader;

public final class ControlWorkload {
    public static void main(String[] args) throws Exception {
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));
        String line = reader.readLine();
        int iterations = line == null || line.isBlank() ? 12_000_000 : Integer.parseInt(line.trim());
        long checksum = 0;
        for (int i = 1; i <= iterations; i++) {
            checksum += ((long) i * 31L) ^ (i >>> 3);
        }
        System.out.println(checksum);
    }
}
