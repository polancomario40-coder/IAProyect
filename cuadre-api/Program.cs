using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Configuration;
using Microsoft.EntityFrameworkCore;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using System.Text;
using CuadreApi.Data;
using CuadreApi.Providers;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllers();

// Register HttpContextAccessor and ErpConnectionProvider for dynamic database routing
builder.Services.AddHttpContextAccessor();
builder.Services.AddScoped<IErpConnectionProvider, ErpConnectionProvider>();

// Configure EF Core DbContext with DYNAMIC SQL Server connection resolved per-request
builder.Services.AddDbContext<CuadreDbContext>((serviceProvider, options) =>
{
    var connectionProvider = serviceProvider.GetRequiredService<IErpConnectionProvider>();
    options.UseSqlServer(connectionProvider.GetConnectionString());
});

// Configure EF Core DbContext for Auth database connection (CBSRepository)
var authConnectionString = builder.Configuration.GetConnectionString("AuthConnection");
builder.Services.AddDbContext<AuthDbContext>(options =>
    options.UseSqlServer(authConnectionString));

// Configure CORS for local development and production frontends
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontends", policy =>
    {
        policy.WithOrigins(
            "http://localhost:5174", 
            "http://localhost:5175",
            "http://cuadre.sade.com.do",
            "https://cuadre.sade.com.do",
            "http://auth.sade.com.do",
            "https://auth.sade.com.do"
        )
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials();
    });
});

// Configure JWT Authentication matching production configuration
var jwtKey = builder.Configuration["Jwt:Key"];
if (!string.IsNullOrEmpty(jwtKey))
{
    builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
        .AddJwtBearer(options =>
        {
            options.TokenValidationParameters = new TokenValidationParameters
            {
                ValidateIssuer = false,
                ValidateAudience = false,
                ValidateLifetime = true,
                ValidateIssuerSigningKey = true,
                IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey))
            };
        });
}

builder.Services.AddAuthorization();

var app = builder.Build();

// Configure Middlewares
app.UseRouting();

app.UseCors("AllowFrontends");

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

Console.WriteLine("==================================================");
Console.WriteLine("🚀 Cuadre API Service is starting...");
Console.WriteLine("==================================================");

// Remove hardcoded port to allow IIS (InProcess or OutOfProcess) to assign its own port correctly
app.Run();
