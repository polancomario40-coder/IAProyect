using System;
using System.Collections.Generic;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;

namespace SadeSecurity.API.Services
{
    public interface ITokenService
    {
        string GenerateToken(string username, string fullName, string email, int nivel, string companyId, string companyName, string companyConnString);
    }

    public class TokenService : ITokenService
    {
        private readonly IConfiguration _configuration;

        public TokenService(IConfiguration configuration)
        {
            _configuration = configuration;
        }

        public string GenerateToken(string username, string fullName, string email, int nivel, string companyId, string companyName, string companyConnString)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            
            string secretKey = _configuration["Jwt:Key"] ?? "SUPER_SECRET_KEY_FOR_SADE_SECURITY_APP_2026_JWT_TOKEN";
            var key = Encoding.ASCII.GetBytes(secretKey);

            var claims = new List<Claim>
            {
                new Claim(ClaimTypes.Name, username),
                new Claim("FullName", fullName ?? ""),
                new Claim(ClaimTypes.Email, email ?? ""),
                new Claim("Nivel", nivel.ToString()),
            };

            if (!string.IsNullOrEmpty(companyId))
            {
                claims.Add(new Claim("CompanyId", companyId));
                claims.Add(new Claim("CompanyName", companyName ?? ""));
                claims.Add(new Claim("CompanyConnString", companyConnString ?? ""));
            }

            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(claims),
                Expires = DateTime.UtcNow.AddDays(7),
                Issuer = _configuration["Jwt:Issuer"] ?? "SadeSecurityBackend",
                Audience = _configuration["Jwt:Audience"] ?? "SadeSecurityFrontend",
                SigningCredentials = new SigningCredentials(new SymmetricSecurityKey(key), SecurityAlgorithms.HmacSha256Signature)
            };

            var token = tokenHandler.CreateToken(tokenDescriptor);
            return tokenHandler.WriteToken(token);
        }
    }
}
