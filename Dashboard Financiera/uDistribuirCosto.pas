unit uDistribuirCosto;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, uform, DB, Wwdatsrc, ADODB, ufrArbol, StdCtrls, cxStyles,
  cxCustomData, cxGraphics, cxFilter, cxData, cxDataStorage, cxEdit,
  cxDBData, cxDBLookupComboBox, cxGridLevel, cxGridCustomTableView,
  cxGridTableView, cxGridDBTableView, cxClasses, cxControls,
  cxGridCustomView, cxGrid, cxLookAndFeelPainters, cxButtons;

type
  TDistribuirCosto = class(TFForm)
    rsGastos: TADODataSet;
    rsGastosidCentroCosto: TGuidField;
    rsGastosCentroCostoGasto: TStringField;
    rsGastosFecha: TDateTimeField;
    rsGastosidPartida: TStringField;
    rsGastosidDocumento: TGuidField;
    rsGastosReferencia: TStringField;
    rsGastosidTipoDoc: TStringField;
    rsGastosCantidad: TFloatField;
    rsGastosGasto: TBCDField;
    rsGastosidUnidad: TStringField;
    rsGastosNotas: TStringField;
    frArbol1: TfrArbol;
    Label1: TLabel;
    Label2: TLabel;
    ProyectoPartida: TADODataSet;
    ProyectoPartidaidProyectoPartida: TGuidField;
    ProyectoPartidaidProyecto: TGuidField;
    ProyectoPartidaidPartida: TStringField;
    ProyectoPartidaValor: TBCDField;
    ProyectoPartidaProyectoPartida: TStringField;
    ProyectoPartidaCantidad: TFloatField;
    ProyectoPartidaidUnidad: TStringField;
    rsPartidas: TADODataSet;
    rsPartidasidPartida: TStringField;
    rsPartidasPartida: TStringField;
    rsPartidasidUnidad: TStringField;
    cxGrid1: TcxGrid;
    cxGrid1DBTableView1: TcxGridDBTableView;
    cxGrid1DBTableView1idPartida: TcxGridDBColumn;
    cxGrid1DBTableView1DBColumn1: TcxGridDBColumn;
    cxGrid1DBTableView1Cantidad: TcxGridDBColumn;
    cxGrid1DBTableView1CostoUnidad: TcxGridDBColumn;
    cxGrid1DBTableView1Notas: TcxGridDBColumn;
    cxGrid1Level1: TcxGridLevel;
    lTotal: TLabel;
    dsPartidas: TwwDataSource;
    rsUnidad: TADODataSet;
    rsUnidadidUnidad: TStringField;
    rsUnidadUnidad: TStringField;
    rsUnidadidUnidadBase: TStringField;
    rsUnidadidFactor: TFloatField;
    rsUnidadUidUnidad: TGuidField;
    dsUnidad: TDataSource;
    btGuardar: TcxButton;
    btCancelar: TcxButton;
    lTipo: TLabel;
    rsGastosidCostoDocumento: TGuidField;
    procedure FormCreate(Sender: TObject);
    procedure rsGastosNewRecord(DataSet: TDataSet);
    procedure rsGastosidPartidaValidate(Sender: TField);
    procedure btGuardarClick(Sender: TObject);
    procedure btCancelarClick(Sender: TObject);
    procedure rsGastosAfterPost(DataSet: TDataSet);
    procedure rsGastosAfterDelete(DataSet: TDataSet);
    procedure cxGrid1Exit(Sender: TObject);
  private
    FTotalGasto: Currency;
    FFecha: TDateTime;
    FIdDocumento: Variant;
    FReferencia: string;
    FTipoDoc: string;
    procedure SetTotalGasto(const Value: Currency);
    procedure CopiarPartidas(const idCC: Variant);
    procedure FOnSelectNode(const idCC: Variant); 
    procedure Abrir(const idDoc: Variant);
    procedure SetReferencia(const Value: string);
    procedure SetTipoDoc(const Value: string);
    procedure SetIdDocumento(const Value: Variant);
    function CalcularTotal: Currency;
    procedure ValidarTotales;

    { Private declarations }
  public
    { Public declarations }
    PARTIDA_DEFAULT: string;
    property idDocumento: Variant read FIdDocumento write SetIdDocumento;
    property TotalGasto: Currency read FTotalGasto write SetTotalGasto;
    property Fecha: TDateTime read FFecha write FFecha;
    property TipoDocumento: string read FTipoDoc write SetTipoDoc;
    property Referencia: string read FReferencia write SetReferencia;

    procedure Guardar;
    procedure Cancelar;
  end;

var
  DistribuirCosto: TDistribuirCosto;

procedure AbrirGastoDocumento(const idDoc: Variant; const Total: Currency;
                              const Ref: string; const TipoDoc: string; const Fec: TDateTime);

function CrearDistibCosto(const idDoc: Variant; const Total: Currency;
                              const Ref: string; const TipoDoc: string; const Fec: TDateTime): TDistribuirCosto;
implementation

uses Udata;

{$R *.dfm}

procedure AbrirGastoDocumento(const idDoc: Variant; const Total: Currency;
                              const Ref: string; const TipoDoc: string; const Fec: TDateTime);
var
  dcForm: TDistribuirCosto;
begin
  dcForm := TDistribuirCosto.Create(Application);
  try
    dcForm.TotalGasto := Total;
    dcForm.idDocumento := idDoc;
    dcForm.Referencia := Ref;
    dcForm.Fecha := Fec;
    dcForm.TipoDocumento := TipoDoc;
    if dcForm.ShowModal() = mrOk then
      dcForm.Guardar();
  finally
    dcForm.Release();
  end;
end;

function CrearDistibCosto(const idDoc: Variant; const Total: Currency;
                              const Ref: string; const TipoDoc: string; const Fec: TDateTime): TDistribuirCosto;
var
  dcForm: TDistribuirCosto;
begin
  dcForm := TDistribuirCosto.Create(Application);
  dcForm.TotalGasto := Total;
  dcForm.idDocumento := idDoc;
  dcForm.Referencia := Ref;
  dcForm.Fecha := Fec;
  dcForm.TipoDocumento := TipoDoc;
  Result := dcForm;
end;

procedure TDistribuirCosto.FOnSelectNode(const idCC: Variant);
begin
  with rsGastos do begin
    if Active then begin
      Filter := 'IdCentroCosto = ' + VarToStrDef(idCC,'');
      if not Filtered then
        Filtered := True;

      First();
      if Eof then
        CopiarPartidas(idCC);
    end;
  end;
end;

procedure TDistribuirCosto.ValidarTotales;
var
  total: Currency;
begin
  total := CalcularTotal();
  if total > TotalGasto then
    raise Exception.Create('No ha distribuido el total')
  else if total < TotalGasto then
    raise Exception.Create('Ha distribuido mas de el total');
end;

function TDistribuirCosto.CalcularTotal: Currency;
var
  bm: string;
  tot: Currency;
begin
  tot := 0;
  with rsGastos do begin
    DisableControls();
    bm := BookMark;
    try
      Filtered := False;
      First();
      while not Eof do begin
        tot := tot + rsGastosGasto.AsCurrency;
        Next();
      end;
      Filtered := True;
      BookMark := bm;
    finally
      EnableControls();
    end;
  end;
  Result := tot;
end;

procedure TDistribuirCosto.CopiarPartidas(const idCC: Variant);
begin
  with ProyectoPartida do begin
    Close();
    Parameters[1].Value := idCC;
    Open();

    while not Eof do begin
       rsGastos.Append();
       rsGastosidPartida.Value := ProyectoPartidaIdPartida.Value;
       rsGastos.Post();
       Next();
    end;
  end;
end;

procedure TDistribuirCosto.FormCreate(Sender: TObject);
begin
  inherited;
  rsUnidad.Open();
  rsPartidas.Open();
  frArbol1.CommandName := 'proyCentroCostoTree';
  frArbol1.OnSelectedChange := FOnSelectNode;
  frArbol1.FillTree(NULL);
  frArbol1.Tree.FullCollapse();
  PARTIDA_DEFAULT := dm.GetDefaultStr('PARTIDA_DEFAULT');
end;

procedure TDistribuirCosto.SetTotalGasto(const Value: Currency);
begin
  FTotalGasto := Value;
  lTotal.Caption := FormatFloat('##,###,##0.00',Value);
end;

procedure TDistribuirCosto.rsGastosNewRecord(DataSet: TDataSet);
var
  aKey: Variant;
begin
  inherited;
  aKey := frArbol1.KeyActual;
  if aKey = NULL then
    Abort;
  rsGastosidCostoDocumento.asGuid := dm.NewGuid();
  rsGastosidCentroCosto.Value := aKey;
  rsGastosFecha.Value := Fecha;
  rsGastosIdDocumento.Value := idDocumento;
  rsGastosReferencia.Value := Referencia;
  rsGastosCentroCostoGasto.Value := TipoDocumento + ':' + Referencia;
  rsGastosidTipoDoc.Value := TipoDocumento;
  rsGastosCantidad.Value := 1;
  if PARTIDA_DEFAULT <> '' then
    rsGastosidPartida.Value := PARTIDA_DEFAULT;
end;

procedure TDistribuirCosto.rsGastosidPartidaValidate(Sender: TField);
begin
  inherited;
  if rsPartidas.Locate('idPartida',rsGastosIdPartida.Value,[]) then
    rsGastosIdUnidad.Value := rsPartidasIdUnidad.Value;
end;

procedure TDistribuirCosto.btGuardarClick(Sender: TObject);
begin
  inherited;
//  Guardar();
  //Close();
  ModalResult := mrOk;
end;

procedure TDistribuirCosto.Guardar;
var
  flt: Boolean;
begin
  ValidarTotales();

  with rsGastos do begin
    flt := Filtered;
    Filtered := False;
    DisableControls();
    try
      if State in dsEditModes then
        Post();

      First();
      while not Eof do begin
        if rsGastosGasto.AsCurrency > 0.00 then begin
          Edit();
          rsGastosFecha.Value := Fecha;
          rsGastosIdDocumento.Value := idDocumento;
          rsGastosReferencia.Value := Referencia;
          rsGastosCentroCostoGasto.Value := TipoDocumento + ':' + Referencia;
          rsGastosidTipoDoc.Value := TipoDocumento;
          Post();

          Next();
        end
        else
          Delete();
      end;

      UpdateBatch();
    finally
      Filtered := flt;
      EnableControls();
    end;
  end;
end;

procedure TDistribuirCosto.SetReferencia(const Value: string);
begin
  FReferencia := Value;
end;

procedure TDistribuirCosto.SetTipoDoc(const Value: string);
begin
  FTipoDoc := Value;
  lTipo.Caption := Value;
end;

procedure TDistribuirCosto.Abrir(const idDoc: Variant);
var
  i: Integer;
  aKey: TTreeKey;
begin
  with rsGastos do begin
    Close();
    Parameters[1].Value := idDoc;
    Open();

    Filtered := False;
    DisableControls();
    frArbol1.Tree.Items.BeginUpdate();
    try
      for i := 0 to frArbol1.Tree.Items.Count - 1 do begin
        if frArbol1.Tree.Items[i].Data <> nil then begin
          aKey := TTreeKey(frArbol1.Tree.Items[i].Data);
          aKey.Highlighted := Locate('idCentroCosto',aKey.Key,[]);
          if aKey.HighLighted then
            frArbol1.Tree.Items[i].MakeVisible();
        end;
      end;
    finally
      frArbol1.Tree.Items.EndUpdate();
      Filtered := True;
      First();
      EnableControls();
    end;
  end;
end;

procedure TDistribuirCosto.SetIdDocumento(const Value: Variant);
begin
  if (FIdDocumento <> NULL) and (FIdDocumento <> Value) then begin
    FIdDocumento := Value;
    Abrir(Value);
  end;
end;

procedure TDistribuirCosto.Cancelar;
begin
  if rsGastos.Active = False then
    exit;

  if rsGastos.State in dsEditModes then
    rsGastos.Cancel();

  rsGastos.CancelBatch(arAll);
end;

procedure TDistribuirCosto.btCancelarClick(Sender: TObject);
begin
  inherited;
  Cancelar();

  ModalResult := mrCancel;
end;

procedure TDistribuirCosto.rsGastosAfterPost(DataSet: TDataSet);
begin
  inherited;
  frArbol1.HighLighted := True;
end;

procedure TDistribuirCosto.rsGastosAfterDelete(DataSet: TDataSet);
begin
  inherited;
  frArbol1.HighLighted := not rsGastos.IsEmpty; 
end;

procedure TDistribuirCosto.cxGrid1Exit(Sender: TObject);
begin
  inherited;
  if (rsGastosGasto.AsCurrency > 0) and (rsGastos.State in dsEditModes) then
    rsGastos.Post();
end;

end.
