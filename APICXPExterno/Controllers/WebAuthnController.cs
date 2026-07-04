using System;
using System.Linq;
using System.Text;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.EntityFrameworkCore;
using Fido2NetLib;
using Fido2NetLib.Objects;
using CxpApi.Data;
using CxpApi.Models;
using System.Security.Claims;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;

namespace CxpApi.Controllers;

[ApiController]
[Route("api/[controller]")]
public class WebAuthnController : ControllerBase
{
    private readonly IFido2 _fido2;
    private readonly IMemoryCache _cache;
    private readonly AuthDbContext _authDb;
    private readonly IConfiguration _config;

    public WebAuthnController(IFido2 fido2, IMemoryCache cache, AuthDbContext authDb, IConfiguration config)
    {
        _fido2 = fido2;
        _cache = cache;
        _authDb = authDb;
        _config = config;
    }

    [Authorize]
    [HttpPost("init-db")]
    public async Task<IActionResult> InitDb()
    {
        try
        {
            await _authDb.Database.ExecuteSqlRawAsync(@"
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='SegUserWebAuthn' AND xtype='U')
                CREATE TABLE SegUserWebAuthn (
                    Id INT IDENTITY(1,1) PRIMARY KEY,
                    Username NVARCHAR(100) NOT NULL,
                    CredentialId VARBINARY(MAX) NOT NULL,
                    PublicKey VARBINARY(MAX) NOT NULL,
                    UserHandle VARBINARY(MAX) NOT NULL,
                    SignatureCounter BIGINT NOT NULL,
                    CredType NVARCHAR(200),
                    RegDate DATETIME NOT NULL,
                    AaGuid UNIQUEIDENTIFIER NOT NULL
                )
            ");
            return Ok(new { success = true, mensaje = "Tabla SegUserWebAuthn creada iterativamente." });
        }
        catch (Exception ex)
        {
            return BadRequest(new { success = false, mensaje = ex.Message });
        }
    }

    [Authorize]
    [HttpPost("register/options")]
    public async Task<IActionResult> MakeCredentialOptions()
    {
        var username = User.FindFirst(ClaimTypes.NameIdentifier)?.Value ?? User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value;
        if (string.IsNullOrEmpty(username)) return Unauthorized();

        var existingCredentials = await _authDb.SegUserWebAuthn
            .Where(u => u.Username == username)
            .Select(c => new PublicKeyCredentialDescriptor(c.CredentialId))
            .ToListAsync();

        var authenticatorSelection = new AuthenticatorSelection
        {
            UserVerification = UserVerificationRequirement.Preferred
        };

        var encUsername = Encoding.UTF8.GetBytes(username);
        var fido2User = new Fido2User
        {
            Name = username,
            DisplayName = username,
            Id = encUsername
        };

        var options = GetFido2().RequestNewCredential(new RequestNewCredentialParams
        {
            User = fido2User,
            ExcludeCredentials = existingCredentials,
            AuthenticatorSelection = authenticatorSelection,
            AttestationPreference = AttestationConveyancePreference.None
        });
        
        // Almacenar temporalmente las opciones para el proximo request
        _cache.Set($"fido2_options_{username}", options.ToJson(), TimeSpan.FromMinutes(5));

        return Ok(options);
    }

    [Authorize]
    [HttpPost("register")]
    public async Task<IActionResult> MakeCredential([FromBody] AuthenticatorAttestationRawResponse attestationResponse)
    {
        var username = User.FindFirst(ClaimTypes.NameIdentifier)?.Value ?? User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value;
        if (string.IsNullOrEmpty(username)) return Unauthorized();

        if (!_cache.TryGetValue($"fido2_options_{username}", out string optionsJson))
        {
            return BadRequest(new { success = false, mensaje = "Sesión Fido2 expirada. Intente nuevamente." });
        }

        var options = CredentialCreateOptions.FromJson(optionsJson);

        IsCredentialIdUniqueToUserAsyncDelegate callback = async (args, cancellationToken) =>
        {
            var stringId = Convert.ToBase64String(args.CredentialId);
            var usersWithCred = await _authDb.SegUserWebAuthn.ToListAsync(cancellationToken);
            return !usersWithCred.Any(c => Convert.ToBase64String(c.CredentialId) == stringId);
        };

        try
        {
            var success = await GetFido2().MakeNewCredentialAsync(new MakeNewCredentialParams
            {
                AttestationResponse = attestationResponse,
                OriginalOptions = options,
                IsCredentialIdUniqueToUserCallback = callback
            }, HttpContext.RequestAborted);

            var newCred = new SegUserWebAuthn
            {
                Username = username,
                CredentialId = success.Id,
                PublicKey = success.PublicKey,
                UserHandle = success.User.Id,
                SignatureCounter = success.SignCount,
                CredType = "public-key",
                RegDate = DateTime.UtcNow,
                AaGuid = Guid.Empty
            };

            _authDb.SegUserWebAuthn.Add(newCred);
            await _authDb.SaveChangesAsync();

            return Ok(new { success = true, mensaje = "Biometría registrada con éxito." });
        }
        catch (Exception e)
        {
            return BadRequest(new { success = false, mensaje = e.Message });
        }
    }

    [HttpPost("login/options")]
    public async Task<IActionResult> MakeAssertionOptions([FromBody] Dictionary<string, string> dto)
    {
        var username = dto.ContainsKey("username") ? dto["username"] : "";
        if (string.IsNullOrEmpty(username)) return BadRequest(new { success = false, mensaje = "Username required" });

        var credentials = await _authDb.SegUserWebAuthn
            .Where(u => u.Username == username)
            .Select(c => new PublicKeyCredentialDescriptor(c.CredentialId))
            .ToListAsync();

        if (!credentials.Any())
            return BadRequest(new { success = false, mensaje = "Este usuario no tiene biometría configurada." });

        var options = GetFido2().GetAssertionOptions(new GetAssertionOptionsParams 
        {
            AllowedCredentials = credentials,
            UserVerification = UserVerificationRequirement.Preferred
        });

        _cache.Set($"fido2_assert_{username}", options.ToJson(), TimeSpan.FromMinutes(5));

        return Ok(options);
    }

    [HttpPost("login")]
    public async Task<IActionResult> MakeAssertion([FromBody] AuthenticatorAssertionRawResponse clientResponse)
    {
        // En login la asercion trae un userHandle asincrono 
        // Identificaremos el request por el intercept cache
        string username = "";
        string storedOptionsJson = "";

        // Reverse search in cache isn't optimal, but typically frontends pass the username in query or header.
        string base64 = clientResponse.Id.Replace('-', '+').Replace('_', '/');
        switch (base64.Length % 4) { case 2: base64 += "=="; break; case 3: base64 += "="; break; }
        var targetIdBytes = Convert.FromBase64String(base64);
        var credRecord = await _authDb.SegUserWebAuthn.ToListAsync();
        var match = credRecord.FirstOrDefault(c => c.CredentialId.SequenceEqual(targetIdBytes));
        
        if (match == null) return Unauthorized(new { success = false, mensaje = "Credencial Biometrica no reconocida." });
        
        username = match.Username;
        
        if (!_cache.TryGetValue($"fido2_assert_{username}", out storedOptionsJson))
        {
            return BadRequest(new { success = false, mensaje = "Token Fido2 expirado." });
        }

        var options = AssertionOptions.FromJson(storedOptionsJson);

        IsUserHandleOwnerOfCredentialIdAsync callback = async (args, cancellationToken) =>
        {
            var stringId = Convert.ToBase64String(args.CredentialId);
            var stringHandle = Convert.ToBase64String(args.UserHandle);
            
            var allCreds = await _authDb.SegUserWebAuthn.ToListAsync(cancellationToken);
            var cred = allCreds.FirstOrDefault(c => Convert.ToBase64String(c.CredentialId) == stringId);
            
            return cred != null && Convert.ToBase64String(cred.UserHandle) == stringHandle;
        };

        try
        {
            var res = await GetFido2().MakeAssertionAsync(new MakeAssertionParams
            {
                AssertionResponse = clientResponse,
                OriginalOptions = options,
                StoredPublicKey = match.PublicKey,
                StoredSignatureCounter = (uint)match.SignatureCounter,
                IsUserHandleOwnerOfCredentialIdCallback = callback
            }, HttpContext.RequestAborted);

            // Update signature counter
            match.SignatureCounter = res.SignCount;
            await _authDb.SaveChangesAsync();

            // Login exitoso: Generate JWT
            var usuarioDb = await _authDb.Usuarios.FirstOrDefaultAsync(u => u.Username == username);
            if (usuarioDb == null) return Unauthorized();

            var tokenHandler = new JwtSecurityTokenHandler();
            var keyStr = _config["Jwt:Key"];
            var key = Encoding.ASCII.GetBytes(keyStr ?? "");

            var claims = new List<Claim>
            {
                new Claim(JwtRegisteredClaimNames.Sub, usuarioDb.Username?.Trim() ?? ""),
                new Claim(JwtRegisteredClaimNames.Jti, usuarioDb.GuidUserGrp.ToString()),
                new Claim(ClaimTypes.Role, usuarioDb.Nivel.ToString()),
                new Claim(ClaimTypes.Name, usuarioDb.Nombre?.Trim() ?? usuarioDb.Username?.Trim() ?? "")
            };

            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(claims),
                Expires = DateTime.UtcNow.AddHours(8),
                Issuer = _config["Jwt:Issuer"],
                Audience = _config["Jwt:Audience"],
                SigningCredentials = new SigningCredentials(new SymmetricSecurityKey(key), SecurityAlgorithms.HmacSha256Signature)
            };

            var token = tokenHandler.CreateToken(tokenDescriptor);

            return Ok(new
            {
                success = true,
                token = tokenHandler.WriteToken(token),
                usuario = new
                {
                    usuarioDb.Username,
                    usuarioDb.Nombre,
                    usuarioDb.Nivel
                }
            });
        }
        catch (Exception e)
        {
            return BadRequest(new { success = false, mensaje = "Validación biométrica fallida: " + e.Message });
        }
    }

    private IFido2 GetFido2()
    {
        var reqDomain = Request.Host.Host;
        var origin = $"{Request.Scheme}://{Request.Host.Value}";
        
        var fidoConfig = new Fido2Configuration
        {
            ServerDomain = _config["fido2:serverDomain"] ?? reqDomain,
            ServerName = "Dataflow CXP",
            Origins = _config.GetSection("fido2:origins").Get<HashSet<string>>() ?? new HashSet<string> { origin },
            TimestampDriftTolerance = 300000
        };
        return new Fido2(fidoConfig);
    }
}
