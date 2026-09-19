using System;
using System.Text;

namespace SadeSecurity.API.Services
{
    public interface ICryptoService
    {
        string EncryptString(string inStr, ushort key = 2000);
        string DeEncryptString(string inStr, ushort key = 2000);
    }

    public class CryptoService : ICryptoService
    {
        private const ushort C1 = 52845;
        private const ushort C2 = 22719;

        static CryptoService()
        {
            // Register CodePagesProvider to support Windows-1252 encoding
            Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
        }

        private Encoding GetAnsiEncoding()
        {
            try
            {
                return Encoding.GetEncoding(1252); // Windows-1252 (ANSI)
            }
            catch
            {
                return Encoding.ASCII; // Fallback
            }
        }

        public string EncryptString(string inStr, ushort key = 2000)
        {
            if (string.IsNullOrEmpty(inStr)) return "";

            byte[] resultBytes = new byte[inStr.Length];

            for (int i = 0; i < inStr.Length; i++)
            {
                byte originalByte = (byte)inStr[i];
                byte encryptedByte = (byte)(originalByte ^ (key >> 8));
                resultBytes[i] = encryptedByte;
                key = (ushort)((encryptedByte + key) * C1 + C2);
            }

            // Encode as lowercase hex string to match Delphi Format('%.2x')
            StringBuilder sb = new StringBuilder(resultBytes.Length * 2);
            foreach (byte b in resultBytes)
            {
                sb.Append(b.ToString("x2"));
            }

            return sb.ToString();
        }

        public string DeEncryptString(string inStr, ushort key = 2000)
        {
            // Limpiar espacios y caracteres nulos de Delphi
            inStr = inStr?.Replace("\0", "").Trim();
            if (string.IsNullOrWhiteSpace(inStr)) return "";

            // The hex string must have even length
            if (inStr.Length % 2 != 0) return inStr; // O retornar vacio, pero en el ERP retorna la misma cadena

            try 
            {
                int len = inStr.Length;
                byte[] decodedBytes = new byte[len / 2];
                for (int i = 0; i < len; i += 2)
                {
                    decodedBytes[i / 2] = Convert.ToByte(inStr.Substring(i, 2), 16);
                }

                char[] resultStr = new char[decodedBytes.Length];
                for (int i = 0; i < decodedBytes.Length; i++)
                {
                    resultStr[i] = (char)(decodedBytes[i] ^ (key >> 8));
                    key = (ushort)(((decodedBytes[i] + key) * C1 + C2) % 65536);
                }

                return new string(resultStr);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR DeEncryptString]: {ex.Message}");
                return inStr;
            }
        }
    }
}
