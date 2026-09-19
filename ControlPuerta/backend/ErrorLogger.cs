using System;
using System.IO;
using System.Threading.Tasks;

public class ErrorLogger {
    public static void Log(Exception ex) {
        try {
            string path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "error_log.txt");
            File.AppendAllText(path, DateTime.Now.ToString() + ": " + ex.ToString() + Environment.NewLine);
        } catch {}
    }
}
