using CxpApi.Data;
using Microsoft.EntityFrameworkCore;
using CxpApi.Providers;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Fido2NetLib;
using System.Text;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllers();

// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();

// Add HttpContextAccessor to read claims during connection string resolution
builder.Services.AddHttpContextAccessor();
builder.Services.AddScoped<IErpConnectionProvider, ErpConnectionProvider>();

builder.Services.AddHttpClient<CxpApi.Services.DgiiService>();
builder.Services.AddScoped<CxpApi.Services.ICxpExternoService, CxpApi.Services.CxpExternoService>();


builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader();
    });
});

builder.Services.AddMemoryCache();
builder.Services.AddDistributedMemoryCache();
builder.Services.AddSession(options =>
{
    options.IdleTimeout = TimeSpan.FromMinutes(5);
    options.Cookie.HttpOnly = true;
    options.Cookie.IsEssential = true;
});

builder.Services.AddFido2(options =>
{
    options.ServerDomain = "localhost";
    options.ServerName = "Dataflow CXP Passkeys";
    options.Origins = new HashSet<string> { "http://localhost", "https://localhost", "http://localhost:8081", "http://192.168.1.18", "exp://192.168.1.18" };
    options.TimestampDriftTolerance = 300000;
})
.AddCachedMetadataService(config => {});


// Add DbContexts
var authConnectionString = builder.Configuration.GetConnectionString("AuthConnection")
    ?? throw new InvalidOperationException("Connection string 'AuthConnection' not found.");
builder.Services.AddDbContext<AuthDbContext>(options =>
    options.UseSqlServer(authConnectionString));

builder.Services.AddDbContext<AppDbContext>((serviceProvider, options) =>
{
    var connectionProvider = serviceProvider.GetRequiredService<IErpConnectionProvider>();
    options.UseSqlServer(connectionProvider.GetConnectionString());
});

// Configure JWT Authentication
var jwtKey = builder.Configuration["Jwt:Key"];
if (!string.IsNullOrEmpty(jwtKey))
{
    builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
        .AddJwtBearer(options =>
        {
            options.TokenValidationParameters = new TokenValidationParameters
            {
                ValidateIssuer = true,
                ValidateAudience = true,
                ValidateLifetime = true,
                ValidateIssuerSigningKey = true,
                ValidIssuer = builder.Configuration["Jwt:Issuer"],
                ValidAudience = builder.Configuration["Jwt:Audience"],
                IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey))
            };
        });
}

// Add Authorization policies if needed
builder.Services.AddAuthorization();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

// Global Exception Middleware
app.UseExceptionHandler(errorApp =>
{
    errorApp.Run(async context =>
    {
        var exceptionHandlerPathFeature = context.Features.Get<Microsoft.AspNetCore.Diagnostics.IExceptionHandlerPathFeature>();
        if (exceptionHandlerPathFeature?.Error is Exception ex)
        {
            Console.WriteLine($"\n\n[GLOBAL CRASH]: {ex.Message}");
            Console.WriteLine($"[INNER CRASH]: {ex.InnerException?.Message}\n\n");

            if (ex is UnauthorizedAccessException)
            {
                context.Response.StatusCode = StatusCodes.Status401Unauthorized;
                context.Response.ContentType = "application/json";
                await context.Response.WriteAsJsonAsync(new { mensaje = ex.Message });
                return;
            }
        }
        
        context.Response.StatusCode = 500;
        await context.Response.WriteAsJsonAsync(new { error = "Internal server error." });
    });
});

app.UseCors("AllowAll");

app.UseSession();

app.UseAuthentication();
app.UseAuthorization();

// Para servir archivos expuestos en wwwroot (app web)
app.UseDefaultFiles();
app.UseStaticFiles();

app.MapControllers();

// Fallback al HTMl principal de Expo Router / ASP.NET MVC para IIS
app.MapFallbackToFile("index.html");

app.Run();
