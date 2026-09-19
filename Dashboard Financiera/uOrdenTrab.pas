unit uOrdenTrab;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, uformmant2, DB, ADODB, ActnList, ImgList, Wwdatsrc,
  wwSpeedButton, wwDBNavigator, ExtCtrls, wwclearpanel, wwdbedit,
  wwdbdatetimepicker, StdCtrls, Mask, DBCtrls, Buttons, Grids,
  Wwdbigrd, Wwdbgrid, Wwdotdot, Wwdbcomb, wwdblook, ComCtrls, uformmant3,
  ppProd, ppClass, ppReport, ppComm, ppRelatv, ppDB, ppDBPipe, ppCtrls,
  ppPrnabl, ppStrtch, ppMemo, ppBands, ppCache, myChkBox;

type
  TOrdenTrab = class(Tfformmant3)
    Label1: TLabel;
    DBEdit1: TDBEdit;
    DBEdit2: TDBEdit;
    BitBtn1: TBitBtn;
    AGetProyecto: TAction;
    Label12: TLabel;
    OTStatus: TADODataSet;
    Status: TwwDBLookupCombo;
    Label24: TLabel;
    ProyectoAct: TADODataSet;
    dsProyectoAct: TDataSource;
    wwDBEdit10: TwwDBEdit;
    Proyecto: TwwDBEdit;
    BPreAprobar: TwwNavButton;
    Label4: TLabel;
    BAnular: TwwNavButton;
    DBCheckBox11: TDBCheckBox;
    rsRPTOrdenTrab: TADODataSet;
    dsRPTOrdenTrab: TDataSource;
    RPTOrdenTrab: TppReport;
    bPrint: TwwNavButton;
    ppHeaderBand1: TppHeaderBand;
    ppDetailBand1: TppDetailBand;
    ppFooterBand1: TppFooterBand;
    ppDBMemo1: TppDBMemo;
    ppDBMemo2: TppDBMemo;
    ppLine1: TppLine;
    ppLine2: TppLine;
    ppLabel1: TppLabel;
    ppLabel2: TppLabel;
    ppDBMemo3: TppDBMemo;
    ppDBMemo4: TppDBMemo;
    ppLine3: TppLine;
    ppLine4: TppLine;
    ppLabel3: TppLabel;
    ppLabel4: TppLabel;
    ppLabel5: TppLabel;
    ppLabel6: TppLabel;
    ppLine5: TppLine;
    ppLine6: TppLine;
    ppLabel7: TppLabel;
    ppLabel8: TppLabel;
    ppLine7: TppLine;
    ppLine8: TppLine;
    ppLine9: TppLine;
    ppLine10: TppLine;
    ppLine11: TppLine;
    ppLine12: TppLine;
    ppLine14: TppLine;
    ppLine15: TppLine;
    ppLine16: TppLine;
    ppLine17: TppLine;
    ppLine18: TppLine;
    ppLine19: TppLine;
    ppLine20: TppLine;
    ppLine21: TppLine;
    ppLine22: TppLine;
    ppLine23: TppLine;
    ppLine24: TppLine;
    ppLine26: TppLine;
    ppLine27: TppLine;
    ppLabel9: TppLabel;
    ppShape1: TppShape;
    ppDBText1: TppDBText;
    ppShape2: TppShape;
    ppLabel10: TppLabel;
    ppLabel11: TppLabel;
    ppDBText2: TppDBText;
    ppLabel12: TppLabel;
    ppDBText3: TppDBText;
    ppLabel13: TppLabel;
    ppDBText4: TppDBText;
    ppShape3: TppShape;
    rsRPTOrdenTrabidOrdenTrab: TGuidField;
    rsRPTOrdenTrabidOrdenTrabParent: TGuidField;
    rsRPTOrdenTrabOrdenTrabParent: TStringField;
    rsRPTOrdenTrabOrdenTrab: TStringField;
    rsRPTOrdenTrabFCreacion: TDateTimeField;
    rsRPTOrdenTrabFecha: TDateTimeField;
    rsRPTOrdenTrabDesde: TDateTimeField;
    rsRPTOrdenTrabHasta: TDateTimeField;
    rsRPTOrdenTrabHora: TDateTimeField;
    rsRPTOrdenTrabDescripcion: TStringField;
    rsRPTOrdenTrabExterno: TBooleanField;
    rsRPTOrdenTrabOTStatus: TWordField;
    rsRPTOrdenTrabPreAprobadoPor: TStringField;
    rsRPTOrdenTrabAprobadoPor: TStringField;
    rsRPTOrdenTrabSolicitadoPor: TStringField;
    rsRPTOrdenTrabRealizadoPor: TStringField;
    rsRPTOrdenTrabInspeccionadoPor: TStringField;
    rsRPTOrdenTrabidGFH: TStringField;
    rsRPTOrdenTrabidGamasDet: TGuidField;
    rsRPTOrdenTrabInicio: TDateTimeField;
    rsRPTOrdenTrabFin: TDateTimeField;
    rsRPTOrdenTrabUsuario: TStringField;
    rsRPTOrdenTrabReferencia: TStringField;
    rsRPTOrdenTrabOTPrioridadReq: TStringField;
    rsRPTOrdenTrabOTPrioridad: TStringField;
    rsRPTOrdenTrabOTIntervencion: TStringField;
    rsRPTOrdenTrabOTEjecutor: TStringField;
    rsRPTOrdenTrabMaquinaParada: TBooleanField;
    rsRPTOrdenTrabPlanosAnexos: TBooleanField;
    rsRPTOrdenTrabInstrucciones: TStringField;
    rsRPTOrdenTrabHerramientas: TStringField;
    rsRPTOrdenTrabNota: TStringField;
    rsRPTOrdenTrabNotaHistorica: TStringField;
    rsRPTOrdenTrabPCotizacion: TBooleanField;
    rsRPTOrdenTrabPMateriales: TBooleanField;
    rsRPTOrdenTrabPHerramientas: TBooleanField;
    rsRPTOrdenTrabPAnalisis: TBooleanField;
    rsRPTOrdenTrabEPersonalTiempo: TBooleanField;
    rsRPTOrdenTrabECoordinacion: TBooleanField;
    rsRPTOrdenTrabESinPreparacion: TBooleanField;
    rsRPTOrdenTrabPospuesto: TBooleanField;
    rsRPTOrdenTrabidProducto: TStringField;
    rsRPTOrdenTrabOrdenTrabDet: TStringField;
    rsRPTOrdenTrabCantidad: TBCDField;
    ppLabel14: TppLabel;
    ppDBText5: TppDBText;
    ppLabel15: TppLabel;
    ppDBText6: TppDBText;
    ppDBMemo5: TppDBMemo;
    rsRPTOrdenTrabGFH: TStringField;
    ppDBMemo6: TppDBMemo;
    ppLine13: TppLine;
    ppLine25: TppLine;
    ppLine28: TppLine;
    ppLine29: TppLine;
    ppLine30: TppLine;
    ppLine31: TppLine;
    ppLine32: TppLine;
    ppLine33: TppLine;
    ppLine34: TppLine;
    ppLine35: TppLine;
    ppLine36: TppLine;
    ppLabel16: TppLabel;
    ppDBText7: TppDBText;
    ppLabel17: TppLabel;
    ppDBText8: TppDBText;
    ppDBText9: TppDBText;
    ppLabel18: TppLabel;
    ppLabel19: TppLabel;
    ppDBText10: TppDBText;
    ppDBText11: TppDBText;
    ppDBText12: TppDBText;
    ppLabel22: TppLabel;
    ppDBText13: TppDBText;
    ppLabel23: TppLabel;
    ppDBText14: TppDBText;
    ppDBText15: TppDBText;
    ppLabel20: TppLabel;
    ppLine37: TppLine;
    ppLine38: TppLine;
    ppLine39: TppLine;
    ppLine40: TppLine;
    ppLabel21: TppLabel;
    ppLabel24: TppLabel;
    ppLabel25: TppLabel;
    ppLabel26: TppLabel;
    ppLabel27: TppLabel;
    ppLabel28: TppLabel;
    ppDBText16: TppDBText;
    ppDBText17: TppDBText;
    ppDBText18: TppDBText;
    ppLabel29: TppLabel;
    ppDBText19: TppDBText;
    ppLabel30: TppLabel;
    ppDBText20: TppDBText;
    ppLine41: TppLine;
    ppLabel31: TppLabel;
    myDBCheckBox1: TmyDBCheckBox;
    ppLabel32: TppLabel;
    myDBCheckBox2: TmyDBCheckBox;
    ppLabel33: TppLabel;
    rsRPTOrdenTrabPreparacion: TBooleanField;
    myDBCheckBox4: TmyDBCheckBox;
    ppLabel34: TppLabel;
    ppLine42: TppLine;
    ppLine43: TppLine;
    myDBCheckBox3: TmyDBCheckBox;
    ppLabel35: TppLabel;
    ppLabel36: TppLabel;
    ppLabel37: TppLabel;
    myDBCheckBox5: TmyDBCheckBox;
    ppLabel38: TppLabel;
    myDBCheckBox6: TmyDBCheckBox;
    ppLabel39: TppLabel;
    myDBCheckBox7: TmyDBCheckBox;
    ppLabel40: TppLabel;
    myDBCheckBox8: TmyDBCheckBox;
    ppLabel41: TppLabel;
    myDBCheckBox9: TmyDBCheckBox;
    ppLabel42: TppLabel;
    myDBCheckBox11: TmyDBCheckBox;
    ppLabel44: TppLabel;
    myDBCheckBox12: TmyDBCheckBox;
    ppLabel45: TppLabel;
    ppLine44: TppLine;
    ppLine45: TppLine;
    ppLine46: TppLine;
    ppLabel43: TppLabel;
    rsRPTOrdenTrabStatus: TStringField;
    plRPTOrdenTrab: TppDBPipeline;
    ppLabel46: TppLabel;
    ppLabel47: TppLabel;
    ppLabel48: TppLabel;
    ppLabel49: TppLabel;
    ppLabel50: TppLabel;
    ppLabel51: TppLabel;
    ProyectoActidProyecto: TGuidField;
    ProyectoActProyecto: TStringField;
    ProyectoActProyectoDesc: TStringField;
    RSidOrdenTrab: TGuidField;
    RSidOrdenTrabParent: TGuidField;
    RSOrdenTrabParent: TStringField;
    RSOrdenTrab: TStringField;
    RSFecha: TDateTimeField;
    RSHasta: TDateTimeField;
    RSStatus: TWordField;
    RSAprobadoPor: TStringField;
    RSRealizadoPor: TStringField;
    RSInspeccionadoPor: TStringField;
    RSNota: TStringField;
    RSEjecutor: TStringField;
    RSPlanos: TBooleanField;
    RSMateriales: TBooleanField;
    RSHerramientas: TBooleanField;
    RSAnalisis: TBooleanField;
    RSCoordinacion: TBooleanField;
    RSPreparacion: TBooleanField;
    RSPospuesto: TBooleanField;
    RSFechaOriginal: TDateTimeField;
    RSUsuario: TStringField;
    RSDetidGasto: TGuidField;
    RSDetidProyecto: TGuidField;
    RSDetidDocumento: TGuidField;
    RSDetidTipoDoc: TStringField;
    RSDetidPartida: TStringField;
    RSDetFecha: TDateTimeField;
    RSDetGasto: TStringField;
    RSDetCosto: TBCDField;
    RSDetCantidad: TFloatField;
    RSDetReferencia: TStringField;
    RSDetNotas: TStringField;
    RSOrdenTrabDesc: TStringField;
    RSDet3idOrdenTrabDet: TGuidField;
    RSDet3idOrdenTrab: TGuidField;
    RSDet3OrdenTrabDet: TStringField;
    RSDet3Tipo: TStringField;
    RSDet3ID: TGuidField;
    RSDet3Cantidad: TFloatField;
    RSDet3Valor: TBCDField;
    RSDet3idUnidad: TStringField;
    RSDet3LineTotal: TFloatField;
    RSidProyecto: TGuidField;
    Label5: TLabel;
    DBEdit3: TDBEdit;
    DBEdit5: TDBEdit;
    GroupBox1: TGroupBox;
    Label13: TLabel;
    Label14: TLabel;
    Label25: TLabel;
    wwDBDateTimePicker4: TwwDBDateTimePicker;
    wwDBDateTimePicker5: TwwDBDateTimePicker;
    wwDBDateTimePicker1: TwwDBDateTimePicker;
    DBCheckBox5: TDBCheckBox;
    DBCheckBox6: TDBCheckBox;
    DBCheckBox4: TDBCheckBox;
    DBCheckBox1: TDBCheckBox;
    DBCheckBox2: TDBCheckBox;
    Label2: TLabel;
    Procedim: TwwDBEdit;
    Label6: TLabel;
    DBEdit4: TDBEdit;
    Label7: TLabel;
    DBEdit7: TDBEdit;
    Label3: TLabel;
    DBEdit6: TDBEdit;
    OTStatusStatus: TIntegerField;
    OTStatusStatusDesc: TStringField;
    procedure FormCreate(Sender: TObject);
    procedure RSNewRecord(DataSet: TDataSet);
    procedure RSAfterScroll(DataSet: TDataSet);
    procedure AGetProyectoExecute(Sender: TObject);
    procedure FormDestroy(Sender: TObject);
    procedure AprintExecute(Sender: TObject);
    procedure ProyectoDblClick(Sender: TObject);
    procedure RSOrdenTrabParentValidate(Sender: TField);
    procedure AGuardarExecute(Sender: TObject);
  private
    { Private declarations }
  public
    procedure Imprimir(id: variant);
    { Public declarations }
  Protected
     procedure browsebotonstate; override;
     procedure Editbotonstate; override;
     procedure Newbotonstate; override;
     procedure ProyectoActivo();
     procedure UserAutoCodigo; override;
  end;

var
  OrdenTrab: TOrdenTrab;

implementation

uses Udata, UUtiles, uBusqueda, OrdenTrabFind, UProyecto,
  ProyOrdenTrabFind, udmCentroCosto;

{$R *.dfm}


procedure TOrdenTrab.UserAutoCodigo;
begin
  rsOrdenTrab.Value := dm.GetNextCounterSTR ('PROYORDENTRAB');
end;

procedure TOrdenTrab.browsebotonstate;
begin
  inherited;
  AGetProyecto.Enabled := false;
end;

procedure TOrdenTrab.Editbotonstate;
begin
  inherited;
   AGetProyecto.Enabled := false;
end;

procedure TOrdenTrab.Newbotonstate;
begin
  inherited;
  AGetProyecto.Enabled := true;

end;

procedure TOrdenTrab.FormCreate(Sender: TObject);
begin
  MasterField  := 'idOrdenTrab';
  DetailField  := 'idDocumento';
  DetailField3 := 'idOrdenTrab';
  inherited;
  spName := '';
  detalleobligatorio := false;
  tfBusqueda := TFindProyOrdenTrab;
  Busqfield := 'idOrdenTrab';
  OTStatus.Open;
end;

procedure TOrdenTrab.RSNewRecord(DataSet: TDataSet);
begin
  inherited;
  RSidOrdenTrab.AsGuid := dm.NewGuid;
  RSusuario.Value := dm.UsuarioActual;
  RSfecha.Value := dm.DBFecha;
  RSHasta.Value := RSfecha.Value;
  RSStatus.Value := 1;
  RSPospuesto.value := false;
  RSFechaOriginal.Value := rsFecha.value;
  rsPlanos.value := false;
  rsMateriales.value := false;
  rsHerramientas.value := false;
  rsPreparacion.value := false;
  rscoordinacion.value := false;
  rsanalisis.value := false;
end;

procedure TOrdenTrab.RSAfterScroll(DataSet: TDataSet);
begin
  inherited;
  ProyectoActivo();
end;

procedure TOrdenTrab.AGetProyectoExecute(Sender: TObject);
var
  x : Variant;
begin
  inherited;
  x := fbuscar(TBusqueda,'idProyecto', true, 'ProyFindProyecto');
  if x <> Null then Begin
    RSidProyecto.Value := x;
  end else begin
    RSidProyecto.clear;
  end;

  ProyectoActivo();
end;


procedure TOrdenTrab.FormDestroy(Sender: TObject);
begin
  inherited;
  OTStatus.close;
end;

procedure TOrdenTrab.ProyectoActivo();
begin
  if RSidProyecto.isnull then
    ProyectoAct.Parameters[1].Value := null
  else
    ProyectoAct.Parameters[1].Value := RSidProyecto.value;

  if ProyectoAct.active then ProyectoAct.Requery else ProyectoAct.open;
end;

procedure TOrdenTrab.AprintExecute(Sender: TObject);
begin
  inherited;
  Imprimir(rsidOrdenTrab.Value);
end;

procedure TOrdenTrab.Imprimir(id : variant);
begin
  inherited;
  if id = Null then raise exception.create('Seleccione un documento valido para imprimir');
  try
    rsRptOrdenTrab.Close;
    rsRptOrdenTrab.Parameters[1].value := id;
    rsRptOrdenTrab.Open;
    RptOrdenTrab.Print;
  except
    showMessage('Error al imprimir el documento');
  end;
end;


procedure TOrdenTrab.ProyectoDblClick(Sender: TObject);
begin
  inherited;
  if not(rsidProyecto.isnull) then
    ModalShow(TProyecto, ShowFind, rsidProyecto.Value, 'idProyecto', true);
end;

procedure TOrdenTrab.RSOrdenTrabParentValidate(Sender: TField);
var
  h : variant;
begin
  inherited;

  if sender.AsString <> '' then
    h := ReturnVariant('ProyOrdenTrab','idOrdenTrab','OrdenTrab = ''' + Sender.AsString + '''')
  else begin
    if not(rsidOrdenTrabParent.isnull) then rsidOrdentrabParent.Clear;
    exit;
  end;

  if (h = null) then begin
    Raise exception.Create('Esta Orden de Trabajo no existe')
  end
  else if rsidOrdenTrabParent.Value <> H then
    rsidOrdenTrabParent.Value := H;
end;

procedure TOrdenTrab.AGuardarExecute(Sender: TObject);
begin
  inherited;
  if not(CentroCostoUpdate(rsidordentrab.value, rsOrdenTrab.Value, rsOrdenTrabDesc.Value, 'OT-Proyecto',rsOrdenTrabParent.value, (rsStatus.value <> 3))) then
    raise exception.create('Error al actualizar el centro de costos');
end;

end.
