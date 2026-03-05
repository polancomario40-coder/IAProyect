using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CxpApi.Migrations
{
    /// <inheritdoc />
    public partial class InitialErp : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_cxpdocumentos_cxpsuplidores_IdSuplidor",
                table: "cxpdocumentos");

            migrationBuilder.DropTable(
                name: "usuarios_movil");

            migrationBuilder.DropPrimaryKey(
                name: "PK_cxpdocumentos",
                table: "cxpdocumentos");

            migrationBuilder.DropIndex(
                name: "IX_cxpdocumentos_IdSuplidor_NumeroDocumento",
                table: "cxpdocumentos");

            migrationBuilder.DropColumn(
                name: "Estado",
                table: "cxpdocumentos");

            migrationBuilder.DropColumn(
                name: "TipoDocumento",
                table: "cxpdocumentos");

            migrationBuilder.DropColumn(
                name: "UsuarioCreacionId",
                table: "cxpdocumentos");

            migrationBuilder.RenameTable(
                name: "cxpdocumentos",
                newName: "cxpdocumento");

            migrationBuilder.RenameColumn(
                name: "Telefono",
                table: "cxpsuplidores",
                newName: "TipoImpuesto");

            migrationBuilder.RenameColumn(
                name: "Estado",
                table: "cxpsuplidores",
                newName: "PedirNCF");

            migrationBuilder.RenameColumn(
                name: "NumeroDocumento",
                table: "cxpdocumento",
                newName: "Usuario");

            migrationBuilder.RenameColumn(
                name: "NCF",
                table: "cxpdocumento",
                newName: "CompFiscal");

            migrationBuilder.RenameColumn(
                name: "Monto",
                table: "cxpdocumento",
                newName: "Valor");

            migrationBuilder.RenameColumn(
                name: "FechaCreacion",
                table: "cxpdocumento",
                newName: "FechaStatus");

            migrationBuilder.RenameColumn(
                name: "Comentarios",
                table: "cxpdocumento",
                newName: "Concepto");

            migrationBuilder.RenameColumn(
                name: "Balance",
                table: "cxpdocumento",
                newName: "Total");

            migrationBuilder.AddColumn<int>(
                name: "DiasCredito",
                table: "cxpsuplidores",
                type: "int",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "EMail",
                table: "cxpsuplidores",
                type: "nvarchar(100)",
                maxLength: 100,
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "Estatus",
                table: "cxpsuplidores",
                type: "bit",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<string>(
                name: "FormaPago",
                table: "cxpsuplidores",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Grupo",
                table: "cxpsuplidores",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "IdMoneda",
                table: "cxpsuplidores",
                type: "int",
                nullable: true);

            migrationBuilder.AddColumn<decimal>(
                name: "LimiteCredito",
                table: "cxpsuplidores",
                type: "decimal(18,2)",
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "MostrarEnCXP",
                table: "cxpsuplidores",
                type: "bit",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<string>(
                name: "Telefono1",
                table: "cxpsuplidores",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "Cancelado",
                table: "cxpdocumento",
                type: "bit",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "FechaEmision",
                table: "cxpdocumento",
                type: "datetime2",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<DateTime>(
                name: "FechaRegistro",
                table: "cxpdocumento",
                type: "datetime2",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<Guid>(
                name: "GUIDDocumento",
                table: "cxpdocumento",
                type: "uniqueidentifier",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            migrationBuilder.AddColumn<decimal>(
                name: "MontoImpuestos",
                table: "cxpdocumento",
                type: "decimal(18,2)",
                nullable: false,
                defaultValue: 0m);

            migrationBuilder.AddColumn<string>(
                name: "Nombre",
                table: "cxpdocumento",
                type: "nvarchar(200)",
                maxLength: 200,
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "PendEnvioEcf",
                table: "cxpdocumento",
                type: "bit",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<bool>(
                name: "PendValidacion",
                table: "cxpdocumento",
                type: "bit",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<string>(
                name: "RNC",
                table: "cxpdocumento",
                type: "nvarchar(20)",
                maxLength: 20,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Referencia",
                table: "cxpdocumento",
                type: "nvarchar(100)",
                maxLength: 100,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Status",
                table: "cxpdocumento",
                type: "nvarchar(10)",
                maxLength: 10,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<DateTime>(
                name: "Vencimiento",
                table: "cxpdocumento",
                type: "datetime2",
                nullable: true);

            migrationBuilder.AddPrimaryKey(
                name: "PK_cxpdocumento",
                table: "cxpdocumento",
                column: "IdDocumento");

            migrationBuilder.CreateIndex(
                name: "IX_cxpdocumento_IdSuplidor_Referencia",
                table: "cxpdocumento",
                columns: new[] { "IdSuplidor", "Referencia" },
                unique: true,
                filter: "[Referencia] IS NOT NULL");

            migrationBuilder.AddForeignKey(
                name: "FK_cxpdocumento_cxpsuplidores_IdSuplidor",
                table: "cxpdocumento",
                column: "IdSuplidor",
                principalTable: "cxpsuplidores",
                principalColumn: "IdSuplidor",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_cxpdocumento_cxpsuplidores_IdSuplidor",
                table: "cxpdocumento");

            migrationBuilder.DropPrimaryKey(
                name: "PK_cxpdocumento",
                table: "cxpdocumento");

            migrationBuilder.DropIndex(
                name: "IX_cxpdocumento_IdSuplidor_Referencia",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "DiasCredito",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "EMail",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "Estatus",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "FormaPago",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "Grupo",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "IdMoneda",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "LimiteCredito",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "MostrarEnCXP",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "Telefono1",
                table: "cxpsuplidores");

            migrationBuilder.DropColumn(
                name: "Cancelado",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "FechaEmision",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "FechaRegistro",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "GUIDDocumento",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "MontoImpuestos",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "Nombre",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "PendEnvioEcf",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "PendValidacion",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "RNC",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "Referencia",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "Status",
                table: "cxpdocumento");

            migrationBuilder.DropColumn(
                name: "Vencimiento",
                table: "cxpdocumento");

            migrationBuilder.RenameTable(
                name: "cxpdocumento",
                newName: "cxpdocumentos");

            migrationBuilder.RenameColumn(
                name: "TipoImpuesto",
                table: "cxpsuplidores",
                newName: "Telefono");

            migrationBuilder.RenameColumn(
                name: "PedirNCF",
                table: "cxpsuplidores",
                newName: "Estado");

            migrationBuilder.RenameColumn(
                name: "Valor",
                table: "cxpdocumentos",
                newName: "Monto");

            migrationBuilder.RenameColumn(
                name: "Usuario",
                table: "cxpdocumentos",
                newName: "NumeroDocumento");

            migrationBuilder.RenameColumn(
                name: "Total",
                table: "cxpdocumentos",
                newName: "Balance");

            migrationBuilder.RenameColumn(
                name: "FechaStatus",
                table: "cxpdocumentos",
                newName: "FechaCreacion");

            migrationBuilder.RenameColumn(
                name: "Concepto",
                table: "cxpdocumentos",
                newName: "Comentarios");

            migrationBuilder.RenameColumn(
                name: "CompFiscal",
                table: "cxpdocumentos",
                newName: "NCF");

            migrationBuilder.AddColumn<string>(
                name: "Estado",
                table: "cxpdocumentos",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "TipoDocumento",
                table: "cxpdocumentos",
                type: "nvarchar(50)",
                maxLength: 50,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<int>(
                name: "UsuarioCreacionId",
                table: "cxpdocumentos",
                type: "int",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddPrimaryKey(
                name: "PK_cxpdocumentos",
                table: "cxpdocumentos",
                column: "IdDocumento");

            migrationBuilder.CreateTable(
                name: "usuarios_movil",
                columns: table => new
                {
                    IdUsuario = table.Column<int>(type: "int", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    Activo = table.Column<bool>(type: "bit", nullable: false),
                    PasswordHash = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    Rol = table.Column<string>(type: "nvarchar(50)", maxLength: 50, nullable: false),
                    Username = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_usuarios_movil", x => x.IdUsuario);
                });

            migrationBuilder.CreateIndex(
                name: "IX_cxpdocumentos_IdSuplidor_NumeroDocumento",
                table: "cxpdocumentos",
                columns: new[] { "IdSuplidor", "NumeroDocumento" },
                unique: true);

            migrationBuilder.AddForeignKey(
                name: "FK_cxpdocumentos_cxpsuplidores_IdSuplidor",
                table: "cxpdocumentos",
                column: "IdSuplidor",
                principalTable: "cxpsuplidores",
                principalColumn: "IdSuplidor",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
