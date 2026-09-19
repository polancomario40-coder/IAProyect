unit uMantPresupuesto;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, uMantClass, cxLookAndFeelPainters, ImgList, ActnList, DB,
  Wwdatsrc, StdCtrls, cxButtons, Gradient, ADODB, uArbolProyectos,
  cxStyles, cxCustomData, cxGraphics, cxFilter, cxData, cxDataStorage,
  cxEdit, cxDBData, cxGridLevel, cxClasses, cxControls, cxGridCustomView,
  cxGridCustomTableView, cxGridTableView, cxGridDBTableView, cxGrid,
  cxMaskEdit, cxDropDownEdit, cxLookupEdit, cxDBLookupEdit,
  cxDBLookupComboBox, cxContainer, cxTextEdit, cxDBEdit, ppDB, ppBands,
  ppCache, ppClass, ppProd, ppReport, ppComm, ppRelatv, ppDBPipe, ppCtrls,
  ppVar, ppPrnabl;

type
  TMantPresupuesto = class(TMantClass)
    ArbolProyectos1: TArbolProyectos;
    rsPartidas: TADODataSet;
    cxGrid1DBTableView1: TcxGridDBTableView;
    cxGrid1Level1: TcxGridLevel;
    cxGrid1: TcxGrid;
    RS: TADODataSet;
    RSidPresupuesto: TGuidField;
    RSidProyecto: TGuidField;
    RSPresupuesto: TStringField;
    rsListaProyectos: TADODataSet;
    rsListaProyectosidProyecto: TGuidField;
    rsListaProyectosProyecto: TStringField;
    rsListaProyectosProyectoDesc: TStringField;
    Label1: TLabel;
    Label2: TLabel;
    RSidPresupuestoTipo: TStringField;
    rsTipo: TADODataSet;
    rsTipoidPresupuestoTipo: TStringField;
    rsTipoPresupuestoTipo: TStringField;
    edPresupuesto: TcxDBTextEdit;
    cxDBLookupComboBox1: TcxDBLookupComboBox;
    dsControles: TwwDataSource;
    Label3: TLabel;
    cxDBLookupComboBox2: TcxDBLookupComboBox;
    dsTipos: TwwDataSource;
    cxButton1: TcxButton;
    rsDet: TADODataSet;
    rsDetidPresupuestoDet: TGuidField;
    rsDetidPresupuesto: TGuidField;
    rsDetidProyecto: TGuidField;
    rsDetidPartida: TStringField;
    rsDetCantidad: TFloatField;
    rsDetCostoUnidad: TFloatField;
    rsDetNotas: TStringField;
    dsDet: TwwDataSource;
    cxGrid1DBTableView1idPartida: TcxGridDBColumn;
    cxGrid1DBTableView1Cantidad: TcxGridDBColumn;
    cxGrid1DBTableView1CostoUnidad: TcxGridDBColumn;
    cxGrid1DBTableView1Notas: TcxGridDBColumn;
    dsPartidas: TDataSource;
    rsPartidasidPartida: TStringField;
    rsPartidasPartida: TStringField;
    rsPartidasidUnidad: TStringField;
    rsDetidUnidad: TStringField;
    rsUnidad: TADODataSet;
    rsUnidadidUnidad: TStringField;
    rsUnidadUnidad: TStringField;
    rsUnidadidUnidadBase: TStringField;
    rsUnidadidFactor: TFloatField;
    rsUnidadUidUnidad: TGuidField;
    dsUnidad: TDataSource;
    cxGrid1DBTableView1DBColumn1: TcxGridDBColumn;
    rsRPT: TADODataSet;
    rsRPTidPresupuesto: TGuidField;
    rsRPTidProyecto: TGuidField;
    rsRPTPresupuesto: TStringField;
    rsRPTidPresupuestoTipo: TStringField;
    rsRPTProyecto: TStringField;
    rsRPTProyectoDesc: TStringField;
    rsRPTidPartida: TStringField;
    rsRPTPartida: TStringField;
    rsRPTidUnidad: TStringField;
    rsRPTCantidad: TFloatField;
    rsRPTCostoUnidad: TFloatField;
    rsRPTDetProyecto: TStringField;
    rsRPTDetProyectoDesc: TStringField;
    dsRPT: TDataSource;
    plRPT: TppDBPipeline;
    Report: TppReport;
    rsRPTNotas: TStringField;
    rsRPTTotal: TFloatField;
    ppHeaderBand1: TppHeaderBand;
    ppDetailBand1: TppDetailBand;
    ppFooterBand1: TppFooterBand;
    ppTitleBand1: TppTitleBand;
    ppGroup1: TppGroup;
    ppGroupFooterBand1: TppGroupFooterBand;
    ppGroupHeaderBand1: TppGroupHeaderBand;
    ppLabel1: TppLabel;
    ppSystemVariable1: TppSystemVariable;
    ppSystemVariable2: TppSystemVariable;
    ppDBText1: TppDBText;
    ppDBText2: TppDBText;
    ppLabel2: TppLabel;
    ppDBText3: TppDBText;
    ppLabel3: TppLabel;
    ppDBText4: TppDBText;
    ppLabel4: TppLabel;
    ppDBText5: TppDBText;
    ppLabel5: TppLabel;
    ppDBText6: TppDBText;
    ppLabel6: TppLabel;
    ppLine5: TppLine;
    ppDBText7: TppDBText;
    ppDBText8: TppDBText;
    ppDBText9: TppDBText;
    ppDBText10: TppDBText;
    ppDBText11: TppDBText;
    ppLabel7: TppLabel;
    ppShape1: TppShape;
    ppShape2: TppShape;
    ppLine3: TppLine;
    ppLine4: TppLine;
    ppLine6: TppLine;
    ppLine7: TppLine;
    ppLine8: TppLine;
    ppLine9: TppLine;
    ppLine10: TppLine;
    ppLine11: TppLine;
    ppLine12: TppLine;
    ppLine13: TppLine;
    ppLine1: TppLine;
    ProyectoPartida: TADODataSet;
    ProyectoPartidaidProyectoPartida: TGuidField;
    ProyectoPartidaidProyecto: TGuidField;
    ProyectoPartidaidPartida: TStringField;
    ProyectoPartidaValor: TBCDField;
    ProyectoPartidaProyectoPartida: TStringField;
    ProyectoPartidaCantidad: TFloatField;
    ProyectoPartidaidUnidad: TStringField;
    procedure RSidProyectoValidate(Sender: TField);
    procedure FormCreate(Sender: TObject);
    procedure rsDetNewRecord(DataSet: TDataSet);
    procedure RSNewRecord(DataSet: TDataSet);
    procedure rsDetidPartidaValidate(Sender: TField);
    procedure cxGrid1Enter(Sender: TObject);
    procedure cxGrid1Exit(Sender: TObject);
  private
    procedure ActualizarProyectos;
    procedure FOnSelectNode(const idProy: TGUID);
    procedure LimpiarPresupuesto;
    procedure CopiarPartidasProyecto(const idProy: TGUID);
    { Private declarations }
  protected
    procedure doNuevo; override;
    procedure doGuardar; override;
    procedure doCancelar; override;
    procedure doEditar; override;
    procedure doPrint; override;

    function Localizar(const id: Variant): boolean; override;
  public
    { Public declarations }
  end;

var
  MantPresupuesto: TMantPresupuesto;

implementation

uses Udata, UUtiles, uBusqueda;

{$R *.dfm}

procedure TMantPresupuesto.doCancelar;
begin
  inherited;
  if rs.State in dsEditModes then
    rs.Cancel();
  rs.CancelBatch(arAll);

  if rsDet.State in dsEditModes then
    rsDet.Cancel();  
  rsDet.CancelBatch();

  dsDet.AutoEdit := False;
  cxGrid1.Enabled := False;
end;

procedure TMantPresupuesto.doGuardar;
begin
  inherited;
  if appEstado <> appBrowse then begin
    if rs.State in dsEditModes then
      rs.Post();
      
    rs.UpdateBatch(arAll);
    if rsDet.State in dsEditModes then
      rsdet.Post();

    LimpiarPresupuesto();
    
    rsDet.UpdateBatch(arAll);                                   
  end;
  dsDet.AutoEdit := False;
  cxGrid1.Enabled := False;
end;

procedure TMantPresupuesto.doNuevo;
begin
  inherited;
  rs.Append();

  with rsDet do begin
    Close();
    Parameters[1].Value := null;
    Open();
  end;

  dsdet.AutoEdit := True;
  cxGrid1.Enabled := True;
end;

procedure TMantPresupuesto.RSidProyectoValidate(Sender: TField);
begin
  inherited;
  ActualizarProyectos();
end;

procedure TMantPresupuesto.ActualizarProyectos;
var
  Numero: string;
begin
  if rsListaProyectos.Locate('idProyecto',rsIdProyecto.Value,[]) then begin
    Numero := rsListaProyectosProyecto.Value;

    ArbolProyectos1.FillTree(Numero + '%');
    ArbolProyectos1.KeyActual := rsIdProyecto.AsGuid;
  end;
end;

procedure TMantPresupuesto.CopiarPartidasProyecto(const idProy: TGuid);
begin
  with ProyectoPartida do begin
    Close();
    Parameters[1].Value := GuidToString(idProy);
    Open();

    while not Eof do begin
       rsDet.Append();
       rsDetidPartida.Value := ProyectoPartidaIdPartida.Value;
       rsDet.Post();
       Next();
    end;
  end;
end;

procedure TMantPresupuesto.FormCreate(Sender: TObject);
begin
  inherited;
  rsTipo.Open();
  rs.Open();
  rsListaProyectos.Open();
  rsPartidas.Open();
  rsUnidad.Open();

  spName := 'ProyPresupuestoFind';
  OcultarC1 := True;
  TFBusqueda := TBusqueda;
  Busqfield := 'idPresupuesto';
  ArbolProyectos1.OnSelectedChange := FOnSelectNode;
end;

function TMantPresupuesto.Localizar(const id: Variant): boolean;
begin
  with rs do begin
    Close();
    Parameters[1].Value := id;
    Open();

    result := not Eof;
  end;

  with rsdet do begin
    Close();
    Parameters[1].Value := id;
    Open();
  end;

  ActualizarProyectos();
  cxGrid1.Enabled := False;
end;

procedure TMantPresupuesto.rsDetNewRecord(DataSet: TDataSet);
begin
  inherited;
  if ArbolProyectos1.NodoActual = nil then
    Abort;
    
  rsDetIdPresupuesto.Value := rsIdPresupuesto.Value;
  rsDetIdPresupuestoDet.AsGuid := dm.NewGuid();
  rsDetIdProyecto.Value := GuidToString(ArbolProyectos1.NodoActual.idProyecto);
  rsDetCostoUnidad.Value := 0.00;
end;

procedure TMantPresupuesto.RSNewRecord(DataSet: TDataSet);
begin
  inherited;
  rsIdPresupuesto.AsGuid := dm.NewGuid();
end;

procedure TMantPresupuesto.FOnSelectNode(const idProy: TGUID);
begin
    with rsDet do begin
    if Active then begin
      Filter := 'IdProyecto = ' + GuidToString(idProy);
      if not Filtered then
        Filtered := True;

      rsDet.First();
      if Eof then
        CopiarPartidasProyecto(idProy);
    end;
  end;
end;

procedure TMantPresupuesto.LimpiarPresupuesto;
//var
//  Numero: string;
begin
  with rsDet do begin
    DisableControls();
    Filtered := False;
    try     
      First();
      while not Eof do begin
        if rsDetCostoUnidad.AsFloat = 0.0 then
          Delete()
        else begin
        //if AnsiStartsText()
          Next();
        end;
      end;
    finally
      Filtered := True;
      EnableControls();
    end;      
  end;
end;

procedure TMantPresupuesto.doEditar;
begin
  inherited;
  dsdet.AutoEdit := True;
  cxGrid1.Enabled := True;
end;

procedure TMantPresupuesto.rsDetidPartidaValidate(Sender: TField);
begin
  inherited;
  if rsPartidas.Locate('idPartida',rsDetIdPartida.Value,[]) then
    rsDetIdUnidad.Value := rsPartidasIdUnidad.Value;
end;

procedure TMantPresupuesto.cxGrid1Enter(Sender: TObject);
begin
  inherited;
  if appEstado <> appBrowse then begin
    Enter2Tab := False;
    if rsDet.RecordCount = 0 then
      rsDet.Append();
  end;
end;

procedure TMantPresupuesto.cxGrid1Exit(Sender: TObject);
begin
  inherited;
  Enter2Tab := True;
end;

procedure TMantPresupuesto.doPrint;
begin
  inherited;
  with rsRPT do begin
    Close();
    Parameters[1].Value := RSidPresupuesto.Value;
    Open();
  end;
  Report.Print();
end;

end.
