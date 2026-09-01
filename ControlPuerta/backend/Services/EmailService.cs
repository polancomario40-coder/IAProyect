using MailKit.Net.Smtp;
using MailKit.Security;
using MimeKit;
using MimeKit.Text;

namespace ControlPuertaAPI.Services;

/// <summary>
/// Contrato del servicio de email. Permite cambiar la implementación
/// (real SMTP, log, Mailtrap, SendGrid, etc.) sin tocar los controladores.
/// </summary>
public interface IEmailService
{
    Task<bool> EnviarConduceFirmadoAsync(
        string destinatario,
        string[] cc,
        string asunto,
        string cuerpoHtml,
        byte[]? adjunto,
        string nombreAdjunto);
}

/// <summary>
/// Implementación del servicio de email.
/// - Si Smtp:Enabled = true  → envía vía MailKit al servidor SMTP configurado.
/// - Si Smtp:Enabled = false → registra el payload en consola/log (modo dev).
/// </summary>
public class EmailService : IEmailService
{
    private readonly IConfiguration _config;
    private readonly ILogger<EmailService> _logger;

    public EmailService(IConfiguration config, ILogger<EmailService> logger)
    {
        _config = config;
        _logger = logger;
    }

    public async Task<bool> EnviarConduceFirmadoAsync(
        string   destinatario,
        string[] cc,
        string   asunto,
        string   cuerpoHtml,
        byte[]?  adjunto,
        string   nombreAdjunto)
    {
        bool smtpEnabled   = _config.GetValue<bool>("Smtp:Enabled", false);
        bool logToConsole  = _config.GetValue<bool>("Smtp:LogToConsole", true);

        // ── Modo desarrollo: sólo log ─────────────────────────────────────────
        if (!smtpEnabled)
        {
            if (logToConsole)
            {
                _logger.LogInformation(
                    "[EMAIL-SIM] Para: {To} | CC: {CC} | Asunto: {Subject} | Adjunto: {Att} ({Size} bytes)",
                    destinatario,
                    string.Join(", ", cc),
                    asunto,
                    nombreAdjunto,
                    adjunto?.Length ?? 0
                );
                _logger.LogInformation("[EMAIL-SIM] Cuerpo HTML:\n{Body}", cuerpoHtml);
            }
            return true; // Simula éxito en dev
        }

        // ── Modo producción: envío SMTP real con MailKit ──────────────────────
        try
        {
            var host     = _config["Smtp:Host"]     ?? throw new Exception("Smtp:Host no configurado.");
            var port     = _config.GetValue<int>("Smtp:Port", 587);
            var useSsl   = _config.GetValue<bool>("Smtp:UseSsl", true);
            var username = _config["Smtp:Username"] ?? "";
            var password = _config["Smtp:Password"] ?? "";
            var from     = _config["Smtp:FromAddress"] ?? username;
            var fromName = _config["Smtp:FromName"] ?? "Control de Puerta SADE";

            var message = new MimeMessage();
            message.From.Add(new MailboxAddress(fromName, from));
            message.To.Add(MailboxAddress.Parse(destinatario));

            foreach (var ccAddr in cc.Where(s => !string.IsNullOrWhiteSpace(s)))
                message.Cc.Add(MailboxAddress.Parse(ccAddr.Trim()));

            message.Subject = asunto;

            var bodyBuilder = new BodyBuilder { HtmlBody = cuerpoHtml };

            if (adjunto is { Length: > 0 })
                bodyBuilder.Attachments.Add(nombreAdjunto, adjunto, ContentType.Parse("image/jpeg"));

            message.Body = bodyBuilder.ToMessageBody();

            using var smtpClient = new SmtpClient();
            await smtpClient.ConnectAsync(host, port,
                useSsl ? SecureSocketOptions.StartTls : SecureSocketOptions.None);

            if (!string.IsNullOrEmpty(username))
                await smtpClient.AuthenticateAsync(username, password);

            await smtpClient.SendAsync(message);
            await smtpClient.DisconnectAsync(true);

            _logger.LogInformation("[EMAIL] Correo enviado a {To} — Asunto: {Subject}", destinatario, asunto);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[EMAIL] Error enviando correo a {To}", destinatario);
            return false;
        }
    }
}
