using System.Text;
using ControlPuertaAPI.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

// ─── Servicios ────────────────────────────────────────────────────────────────
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new() { Title = "Control de Puerta API", Version = "v1" });
    // Soporte Bearer en Swagger UI
    c.AddSecurityDefinition("Bearer", new Microsoft.OpenApi.Models.OpenApiSecurityScheme
    {
        Name = "Authorization",
        Type = Microsoft.OpenApi.Models.SecuritySchemeType.Http,
        Scheme = "Bearer",
        BearerFormat = "JWT",
        In = Microsoft.OpenApi.Models.ParameterLocation.Header,
        Description = "Ingrese el token JWT generado por SegSAde. Ejemplo: 'eyJhbGci...'"
    });
    c.AddSecurityRequirement(new Microsoft.OpenApi.Models.OpenApiSecurityRequirement
    {
        {
            new Microsoft.OpenApi.Models.OpenApiSecurityScheme
            {
                Reference = new Microsoft.OpenApi.Models.OpenApiReference
                {
                    Type = Microsoft.OpenApi.Models.ReferenceType.SecurityScheme,
                    Id = "Bearer"
                }
            },
            Array.Empty<string>()
        }
    });
});

// ─── HttpContextAccessor (para obtener IP del cliente en servicios) ─────────
builder.Services.AddHttpContextAccessor();

// ─── HttpClient para Azure AI Document Intelligence ──────────────────────────
builder.Services.AddHttpClient("AzureDocIntelligence", client =>
{
    client.Timeout = TimeSpan.FromSeconds(60);
});

// ─── Servicios de negocio ────────────────────────────────────────────────────
builder.Services.AddSingleton<IConnectionFactory, ConnectionFactory>();
builder.Services.AddScoped<IPuertaDbService, PuertaDbService>();
builder.Services.AddScoped<IEvidenciaService, EvidenciaService>();
builder.Services.AddScoped<IOcrService, OcrService>();
builder.Services.AddScoped<IEmailService, EmailService>();

// ─── CORS ─────────────────────────────────────────────────────────────────────
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

// ─── JWT Authentication (comparte la misma clave que SegSAde / APICXPExterno) ─
var jwtKey = builder.Configuration["Jwt:Key"]
    ?? throw new InvalidOperationException("Jwt:Key no configurada en appsettings.");
var jwtIssuer   = builder.Configuration["Jwt:Issuer"]   ?? "CxpApi";
var jwtAudience = builder.Configuration["Jwt:Audience"] ?? "CxpMobileApp";

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.RequireHttpsMetadata = false;
        options.SaveToken = true;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey)),
            ValidateIssuer   = true,
            ValidIssuer      = jwtIssuer,
            ValidateAudience = true,
            ValidAudience    = jwtAudience,
            ValidateLifetime = true,
            ClockSkew        = TimeSpan.Zero
        };
    });

builder.Services.AddAuthorization();

// ─── Build ───────────────────────────────────────────────────────────────────
var app = builder.Build();

// ─── Pipeline ────────────────────────────────────────────────────────────────
app.UseSwagger();
app.UseSwaggerUI(c => c.SwaggerEndpoint("/swagger/v1/swagger.json", "Control de Puerta v1"));

// Manejo global de errores no controlados
app.UseExceptionHandler(errorApp =>
{
    errorApp.Run(async context =>
    {
        var feature = context.Features.Get<Microsoft.AspNetCore.Diagnostics.IExceptionHandlerPathFeature>();
        if (feature?.Error is Exception ex)
        {
            Console.Error.WriteLine($"[ERROR GLOBAL] {ex.GetType().Name}: {ex.Message}");
            Console.Error.WriteLine(ex.StackTrace);
        }
        context.Response.StatusCode  = 500;
        context.Response.ContentType = "application/json";
        await context.Response.WriteAsJsonAsync(new
        {
            success = false,
            mensaje = "Ocurrió un error interno. Contacte al administrador del sistema."
        });
    });
});

app.UseCors("AllowAll");
app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

Console.WriteLine("====================================================");
Console.WriteLine(" Control de Puerta API — SADE ERP");
Console.WriteLine($" Ambiente: {app.Environment.EnvironmentName}");
Console.WriteLine($" URL Swagger: /swagger");
Console.WriteLine("====================================================");

app.Run();
