unit uProyecto;

interface

uses
  Windows, Messages, SysUtils, Classes, Graphics, Controls, Forms, Dialogs,
  Db, DBTables, dxCntner, dxTL, dxDBCtrl, dxDBTL, ComCtrls, ToolWin,
  ExtCtrls, Menus, dxDBTLCl, Buttons, {ImgList,} StdCtrls, DBCtrls, Grids,
  DBGrids, ShellAPI, dxEditor, dxExEdtr, dxEdLib, dxDBELib, ImgList,uform,
  Wwdatsrc, ADODB, Mask, Wwkeycb, wwdblook, wwdbedit, Wwdbigrd, Wwdbgrid,
  dxDBGrid, ActnList, ActnMan, dxGrClms, XPStyleActnCtrls, dxDBEdtr,
  cxControls, cxContainer, cxEdit, cxTextEdit, cxMaskEdit, cxDropDownEdit,
  cxImageComboBox, cxDBEdit, ppStrtch, ppMemo, ppCtrls, ppVar, ppPrnabl,
  ppClass, ppBands, ppCache, ppDB, ppProd, ppReport, ppComm, ppRelatv,
  ppDBPipe, cxLookupEdit, cxDBLookupEdit, cxDBLookupComboBox, cxPC,
  cxCalendar, cxCheckBox, cxMemo, cxStyles, cxCustomData, cxGraphics,
  cxFilter, cxData, cxDataStorage, cxDBData, cxLabel,
  cxGridCustomTableView, cxGridTableView, cxGridDBTableView, cxGridLevel,
  cxClasses, cxGridCustomView, cxGrid, cxNavigator, cxDBNavigator,
  cxLookAndFeelPainters, cxButtons;

type
  TProyecto = class(TFForm)
    Images: TImageList;
    ImageList1: TImageList;
    Panel2: TPanel;
    DBTreeList: TdxDBTreeList;
    ToolBar1: TToolBar;
    btnAdd: TToolButton;
    btnAddChild: TToolButton;
    ToolButton1: TToolButton;
    btnShowGrid: TToolButton;
    ToolButton4: TToolButton;
    btnFullCollapse: TToolButton;
    btnFullExpand: TToolButton;
    Proyecto: TADODataSet;
    DBTreeListColumn1: TdxDBTreeListColumn;
    DBTreeListColumn2: TdxDBTreeListColumn;
    PageControl1: TcxPageControl;
    ActionLst: TActionManager;
    ParentMove: TAction;
    ToolButton2: TToolButton;
    ToolButton3: TToolButton;
    TabSheet1: TcxTabSheet;
    Label1: TLabel;
    Label5: TLabel;
    Label9: TLabel;
    Label11: TLabel;
    Label13: TLabel;
    Label14: TLabel;
    Label8: TLabel;
    Label10: TLabel;
    eproy: TcxDBTextEdit;
    dxDBEdit2: TcxDBTextEdit;
    dxDBEdit3: TcxDBTextEdit;
    dxDBMemo1: TcxDBMemo;
    dxDBMemo2: TcxDBMemo;
    ProyectoidProyecto: TGuidField;
    ProyectoidProyectoParent: TGuidField;
    ProyectoProyecto: TStringField;
    ProyectoProyectoDesc: TStringField;
    ProyectoStatus: TSmallintField;
    ProyectoUbicacion: TStringField;
    ProyectoInicio: TDateTimeField;
    ProyectoFin: TDateTimeField;
    ProyectoNotas: TStringField;
    ProyectoOTData: TStringField;
    Partida: TADODataSet;
    PartidaidPartida: TStringField;
    dsProyectoPartida: TDataSource;
    dxDBCheckEdit1: TcxDBCheckBox;
    ProyectoActivo: TBooleanField;
    TabSheet2: TcxTabSheet;
    Gasto: TADODataSet;
    dsGasto: TDataSource;
    dxDBGrid2: TdxDBGrid;
    GastoidCentroCostoGasto: TGuidField;
    GastoidCentroCosto: TGuidField;
    GastoCentroCostoGasto: TStringField;
    GastoFecha: TDateTimeField;
    GastoidPartida: TStringField;
    GastoidDocumento: TGuidField;
    GastoReferencia: TStringField;
    GastoidTipoDoc: TStringField;
    GastoCantidad: TFloatField;
    GastoGasto: TBCDField;
    GastoidUnidad: TStringField;
    GastoNotas: TStringField;
    dxDBGrid2idCentroCostoGasto: TdxDBGridColumn;
    dxDBGrid2idCentroCosto: TdxDBGridColumn;
    dxDBGrid2CentroCostoGasto: TdxDBGridMaskColumn;
    dxDBGrid2Fecha: TdxDBGridDateColumn;
    dxDBGrid2idPartida: TdxDBGridMaskColumn;
    dxDBGrid2idDocumento: TdxDBGridColumn;
    dxDBGrid2Referencia: TdxDBGridMaskColumn;
    dxDBGrid2idTipoDoc: TdxDBGridMaskColumn;
    dxDBGrid2Cantidad: TdxDBGridMaskColumn;
    dxDBGrid2Gasto: TdxDBGridCurrencyColumn;
    dxDBGrid2idUnidad: TdxDBGridMaskColumn;
    dxDBGrid2Notas: TdxDBGridMaskColumn;
    dxDBDateEdit1: TcxDBDateEdit;
    dxDBDateEdit2: TcxDBDateEdit;
    cxDBImageComboBox1: TcxDBImageComboBox;
    ProyectoNivel: TSmallintField;
    rsReporte: TADODataSet;
    rsReporteidProyecto: TGuidField;
    rsReporteidProyectoParent: TGuidField;
    rsReporteProyecto: TStringField;
    rsReporteProyectoDesc: TStringField;
    rsReporteStatus: TSmallintField;
    rsReporteUbicacion: TStringField;
    rsReporteInicio: TDateTimeField;
    rsReporteFin: TDateTimeField;
    rsReporteNotas: TStringField;
    rsReporteOTData: TStringField;
    rsReporteActivo: TBooleanField;
    rsReporteNivel: TSmallintField;
    rsReporteIdentedCode: TStringField;
    plProyecto: TppDBPipeline;
    dsRep: TDataSource;
    Report: TppReport;
    ppHeaderBand1: TppHeaderBand;
    ppDetailBand1: TppDetailBand;
    ppFooterBand1: TppFooterBand;
    ppTitleBand1: TppTitleBand;
    ppLabel1: TppLabel;
    ppSystemVariable1: TppSystemVariable;
    ppSystemVariable2: TppSystemVariable;
    ppDBText1: TppDBText;
    ppLabel2: TppLabel;
    ppLabel3: TppLabel;
    ppDBText3: TppDBText;
    ppLabel4: TppLabel;
    ppLabel5: TppLabel;
    ppDBText5: TppDBText;
    ppLabel6: TppLabel;
    ppDBText6: TppDBText;
    ppLabel7: TppLabel;
    ppLine1: TppLine;
    ppLine2: TppLine;
    ppDBMemo1: TppDBMemo;
    ppDBMemo2: TppDBMemo;
    rsReporteControl: TBooleanField;
    ToolButton5: TToolButton;
    ProyectoidUnidad: TStringField;
    ProyectoCantidad: TFloatField;
    rsUnidad: TADODataSet;
    rsUnidadidUnidad: TStringField;
    rsUnidadUnidad: TStringField;
    dsUnidad: TDataSource;
    luUnidad: TcxDBLookupComboBox;
    cxDBTextEdit1: TcxDBTextEdit;
    Label2: TLabel;
    rsControles: TADODataSet;
    dsControles: TDataSource;
    rsControlesidProyecto: TGuidField;
    rsControlesProyecto: TStringField;
    rsControlesProyectoDesc: TStringField;
    luControl: TcxLookupComboBox;
    rsReporteDet: TADODataSet;
    dsRepdet: TDataSource;
    plRepdet: TppDBPipeline;
    ReportDet: TppReport;
    ppTitleBand2: TppTitleBand;
    ppHeaderBand2: TppHeaderBand;
    ppLine3: TppLine;
    ppLabel8: TppLabel;
    ppLabel9: TppLabel;
    ppLabel10: TppLabel;
    ppLabel11: TppLabel;
    ppLabel12: TppLabel;
    ppLabel13: TppLabel;
    ppLabel14: TppLabel;
    ppSystemVariable3: TppSystemVariable;
    ppSystemVariable4: TppSystemVariable;
    ppDetailBand2: TppDetailBand;
    ppDBText2: TppDBText;
    ppDBText4: TppDBText;
    ppDBText7: TppDBText;
    ppDBText8: TppDBText;
    ppDBMemo3: TppDBMemo;
    ppDBMemo4: TppDBMemo;
    ppFooterBand2: TppFooterBand;
    ppLine4: TppLine;
    rsReporteDetIdentedCode: TStringField;
    rsReporteDetPadre: TStringField;
    rsReporteDetControl: TBooleanField;
    rsReporteDetidProyecto: TGuidField;
    rsReporteDetidProyectoParent: TGuidField;
    rsReporteDetProyecto: TStringField;
    rsReporteDetProyectoDesc: TStringField;
    rsReporteDetStatus: TSmallintField;
    rsReporteDetUbicacion: TStringField;
    rsReporteDetInicio: TDateTimeField;
    rsReporteDetFin: TDateTimeField;
    rsReporteDetNotas: TStringField;
    rsReporteDetOTData: TStringField;
    rsReporteDetActivo: TBooleanField;
    rsReporteDetNivel: TSmallintField;
    rsReporteDetidUnidad: TStringField;
    rsReporteDetCantidad: TFloatField;
    rsReporteDetidPartida: TStringField;
    rsReporteDetProyectoPartida: TStringField;
    rsReporteDetCantPartida: TFloatField;
    rsReporteDetUnidadPartida: TStringField;
    ppGroup1: TppGroup;
    ppGroupHeaderBand1: TppGroupHeaderBand;
    ppGroupFooterBand1: TppGroupFooterBand;
    ppLabel15: TppLabel;
    ppLabel16: TppLabel;
    ppDBText9: TppDBText;
    ppDBMemo5: TppDBMemo;
    ppLabel17: TppLabel;
    ppLabel18: TppLabel;
    ppDBText10: TppDBText;
    ppDBText11: TppDBText;
    ppLine5: TppLine;
    PopupMenu1: TPopupMenu;
    miResumen: TMenuItem;
    miDetalle: TMenuItem;
    cxGrid1DBTableView1: TcxGridDBTableView;
    cxGrid1Level1: TcxGridLevel;
    cxGrid1: TcxGrid;
    cxGrid1DBTableView1idPartida: TcxGridDBColumn;
    cxGrid1DBTableView1ProyectoPartida: TcxGridDBColumn;
    cxGrid1DBTableView1Cantidad: TcxGridDBColumn;
    cxGrid1DBTableView1idUnidad: TcxGridDBColumn;
    dsPartida: TDataSource;
    PartidaPartida: TStringField;
    PartidaidUnidad: TStringField;
    Acciones: TActionList;
    AAyuda: TAction;
    ANuevo: TAction;
    AEditar: TAction;
    AGuardar: TAction;
    ACancelar: TAction;
    ABorrar: TAction;
    ALocalizar: TAction;
    Asalir: TAction;
    Aprint: TAction;
    AAnular: TAction;
    AAprobacion: TAction;
    btImprimir: TcxButton;
    btNuevo: TcxButton;
    btEditar: TcxButton;
    btCancelar: TcxButton;
    btGuardar: TcxButton;
    btBorrar: TcxButton;
    btSalir: TcxButton;
    rsDet: TADODataSet;
    rsDetidProyectoPartida: TGuidField;
    rsDetidProyecto: TGuidField;
    rsDetidPartida: TStringField;
    rsDetCantidad: TFloatField;
    rsDetidUnidad: TStringField;
    rsDetProyectoPartida: TStringField;
    rsDetCostoUnidad: TBCDField;
    PartidaCostoUnidad: TBCDField;
    PartidaCompuesto: TBooleanField;
    cxGrid1DBTableView1CostoUnidad: TcxGridDBColumn;
    ppLabel19: TppLabel;
    ppDBText12: TppDBText;
    rsReporteDetCostoUnidad: TBCDField;
    rsReporteDetTotalPartida: TFloatField;
    ppDBText13: TppDBText;
    ppLabel20: TppLabel;
    rsReporteDetTotalProyecto: TBCDField;
    ppDBText14: TppDBText;
    dDesde: TcxDateEdit;
    Label3: TLabel;
    Label4: TLabel;
    DHasta: TcxDateEdit;
    procedure FormCreate(Sender: TObject);
    procedure Exit1Click(Sender: TObject);
    procedure FullCollapse1Click(Sender: TObject);
    procedure FullExpand1Click(Sender: TObject);
    procedure Add1Click(Sender: TObject);
    procedure AddChild1Click(Sender: TObject);
    procedure btnShowGridClick(Sender: TObject);
    procedure ProyectoNewRecord(DataSet: TDataSet);
    procedure DBTreeListGetStateIndex(Sender: TObject;
      Node: TdxTreeListNode; var Index: Integer);
    procedure DBTreeListCustomDrawCell(Sender: TObject; ACanvas: TCanvas;
      ARect: TRect; ANode: TdxTreeListNode; AColumn: TdxTreeListColumn;
      ASelected, AFocused, ANewItemRow: Boolean; var AText: String;
      var AColor: TColor; AFont: TFont; var AAlignment: TAlignment;
      var ADone: Boolean);
    procedure FormShow(Sender: TObject);
    procedure ParentMoveExecute(Sender: TObject);
    procedure ProyectoPartidaNewRecord(DataSet: TDataSet);
    procedure ProyectoAfterScroll(DataSet: TDataSet);
    procedure ProyectoAfterPost(DataSet: TDataSet);
    procedure ppDBText1Print(Sender: TObject);
    procedure cxLookupComboBox1PropertiesEditValueChanged(Sender: TObject);
    procedure miDetalleClick(Sender: TObject);
    procedure miResumenClick(Sender: TObject);
    procedure FormKeyDown(Sender: TObject; var Key: Word;
      Shift: TShiftState);
    procedure ANuevoExecute(Sender: TObject);
    procedure AEditarExecute(Sender: TObject);
    procedure AGuardarExecute(Sender: TObject);
    procedure ACancelarExecute(Sender: TObject);
    procedure ABorrarExecute(Sender: TObject);
    procedure AsalirExecute(Sender: TObject);
    procedure AprintExecute(Sender: TObject);
    procedure rsDetidPartidaValidate(Sender: TField);
  private
    FParentValue: Variant;
    FParentLevel: Integer;
    Floading : boolean;
    UNIDAD_DEFECTO: string;
    procedure CargarPartida;
    procedure CargarGastos;
    procedure ImprimirDetalle;
    procedure ImprimirResumen;
    procedure ActualizarCC;

    procedure doNuevo;
    procedure doGuardar;
    procedure doEditar;
    procedure doPrint;
    procedure doBorrar;
    procedure doCancelar;

    procedure browsebotonstate;
    procedure Editbotonstate;
    procedure Newbotonstate; 
  public
    { Public declarations }
  end;

var
  Proyecto: TProyecto;

implementation

uses Variants, UUtiles, Udata, uBusqueda, udmCentroCosto;

{$R *.DFM}

procedure TProyecto.FormCreate(Sender: TObject);
begin
  inherited;
  dDesde.Date := date() - 30;
  dHasta.date := date();
  partida.open;
  //hay una propiedad que hace que se generen los id automaticamente en el tree
  fLoading := true;
  rsControles.Open();
  rsUnidad.Open();
  luControl.EditValue := '%';
  Proyecto.Open;
  rsDet.Open();
  Floading := false;
  CargarPartida;
  CargarGastos;
  btnShowGrid.Down := DBTreeList.ShowGrid;
  UNIDAD_DEFECTO := dm.GetDefaultStr('UNIDAD_PROYECTO');
  TipoDoc := 'Proyecto';
  LogField := 'Proyecto';
  ImageIdField := 'idProyecto';
end;

procedure TProyecto.Exit1Click(Sender: TObject);
begin
  Close;
end;

procedure TProyecto.FullCollapse1Click(Sender: TObject);
begin
  DBTreeList.FullCollapse;
end;

procedure TProyecto.FullExpand1Click(Sender: TObject);
begin
  DBTreeList.FullExpand;
end;

procedure TProyecto.Add1Click(Sender: TObject);
begin
  // add a record
    if ProyectoidProyectoParent.IsNull then begin
      FParentValue := '';
      FParentLevel := 0;
    end
    else begin
      FParentValue := ProyectoidProyectoParent.AsString ;
      FParentLevel := ProyectoNivel.Value;
    end;

  PageControl1.ActivePageIndex := 0;
  Newbotonstate();
  Proyecto.Insert;
//  DBTreeList.ShowEditor;
  Eproy.SetFocus;
end;

procedure TProyecto.AddChild1Click(Sender: TObject);
var
  parentNum: string;
begin
  // add a child record
  FParentValue := TdxDBTreeListNode(DBTreeList.FocusedNode).Id;
  FParentLevel := DBTreeList.FocusedNode.Level + 1;
  parentnum := proyectoProyecto.Value;
  PageControl1.ActivePageIndex := 0;
  Proyecto.Insert;
  proyectoProyecto.Value := parentNum;
  //DBTreeList.ShowEditor;
  Newbotonstate();
  Eproy.SetFocus;
  Eproy.SelStart := Length(Eproy.Text);
end;

procedure TProyecto.btnShowGridClick(Sender: TObject);
begin
  DBTreeList.ShowGrid := btnShowGrid.Down;
end;

procedure TProyecto.ProyectoNewRecord(DataSet: TDataSet);
begin
  if FParentValue <> '' then begin
     ProyectoidProyectoParent.Value := FParentValue;
     ProyectoNivel.Value := FParentLevel;
  end
  else
    ProyectoNivel.Value := 0;

  proyectoidproyecto.AsGuid := dm.NewGuid;
  ProyectoStatus.value := 1;
  ProyectoActivo.Value := true;
  ProyectoCantidad.Value := 1;
  ProyectoidUnidad.Value := UNIDAD_DEFECTO;
end;

procedure TProyecto.DBTreeListGetStateIndex(Sender: TObject;
  Node: TdxTreeListNode; var Index: Integer);
begin
  if Node.Expanded then
    Index := 1
  else
    Index := 0;

  if not node.HasChildren then
    index := 2;
end;

procedure TProyecto.DBTreeListCustomDrawCell(Sender: TObject;
  ACanvas: TCanvas; ARect: TRect; ANode: TdxTreeListNode;
  AColumn: TdxTreeListColumn; ASelected, AFocused, ANewItemRow: Boolean;
  var AText: String; var AColor: TColor; AFont: TFont;
  var AAlignment: TAlignment; var ADone: Boolean);
begin
  inherited;
{  if ANode.Selected then
  begin
     AColor := clYellow;
//     AFont.Style := [fsBold];
     AFont.Color := clBlue;
  end;}
end;

procedure TProyecto.FormShow(Sender: TObject);
begin
  inherited;

  If ShowState = showFind Then
  begin
    If  ((XField <> '') and (XValue <> Null)) and (Not(ds.DataSet.FieldByName(XField).Value = XValue)) Then
       ds.DataSet.Locate(XField, XValue, []);
  end;

end;

procedure TProyecto.ParentMoveExecute(Sender: TObject);
var
  x : variant;
begin
  inherited;
  x := fbuscar(TBusqueda, 'idProyecto', true, 'ProyFindProyecto');
  if x <> Null then
  begin
     Proyecto.Edit;
     ProyectoidProyectoParent.Value := x;
     Proyecto.Post;
  end;
end;

Procedure TProyecto.CargarPartida();
begin
  rsDet.close;
  if ProyectoidProyecto.isnull then exit;
  rsDet.parameters[1].value := ProyectoidProyecto.Value;
  if rsDet.active then rsDet.requery else rsDet.open;
end;

Procedure TProyecto.CargarGastos();
begin
  Gasto.close;
  if ProyectoidProyecto.isnull then exit;
  Gasto.parameters[1].value := ProyectoidProyecto.Value;
  Gasto.parameters[2].value := dDesde.date;
  Gasto.parameters[3].value := dHasta.date;
  if Gasto.active then Gasto.requery else Gasto.open;
end;


procedure TProyecto.ProyectoPartidaNewRecord(DataSet: TDataSet);
begin
  inherited;
  rsDetidProyecto.Value := ProyectoidProyecto.Value;
  rsDetidProyectoPartida.AsGuid := dm.NewGuid;
  rsDetCantidad.Value := 1;
  rsDetProyectoPartida.Value := '';
end;

procedure TProyecto.ProyectoAfterScroll(DataSet: TDataSet);
begin
  inherited;
  if not(floading) then begin
    CargarPartida;
    CargarGastos;
  end;
end;

procedure TProyecto.ProyectoAfterPost(DataSet: TDataSet);
begin
  inherited;
  ActualizarCC();
end;

procedure TProyecto.ActualizarCC;
begin
  inherited;
  if not(CentroCostoUpdate(proyectoidproyecto.Value, proyectoproyecto.Value,
                           proyectoproyectodesc.Value, TipoDoc, '', proyectoactivo.Value,
                           proyectoidProyectoParent.AsString, proyectoOTData.Value)) then
    raise exception.create('Error al actualizar el centro de costos');
end;

procedure TProyecto.ppDBText1Print(Sender: TObject);
begin
  inherited;
  if rsReporteControl.Value then
    ppDBText1.Font.Style := [fsBold]
  else
    ppDBText1.Font.Style := [];
end;

procedure TProyecto.ImprimirDetalle;
begin
  inherited;
{  with rsReporteDet do begin
    Close();
    Parameters[1].Value := luControl.EditValue;
    Open();
  end;
  ReportDet.Print();}
end;

procedure TProyecto.cxLookupComboBox1PropertiesEditValueChanged(
  Sender: TObject);
begin
  inherited;
  with Proyecto do begin
    Close();
    Parameters[1].Value := luControl.EditValue;
    Open();
  end;
end;

procedure TProyecto.miDetalleClick(Sender: TObject);
begin
  inherited;
  ImprimirDetalle();
end;

procedure TProyecto.ImprimirResumen;
begin
  with rsReporte do begin
    Close();
    Parameters[1].Value := luControl.EditValue;
    Open();
  end;
  Report.Print();
end;

procedure TProyecto.miResumenClick(Sender: TObject);
begin
  inherited;
  ImprimirResumen();
end;

procedure TProyecto.FormKeyDown(Sender: TObject; var Key: Word;
  Shift: TShiftState);
begin
  inherited;
  if ActiveControl = cxGrid1 then
    Exit;

  if not (proyecto.State in dsEditModes) then begin
    if Key = vk_insert then
      AddChild1Click(nil);
  end;
end;

procedure TProyecto.doBorrar;
begin
  Proyecto.Delete();
end;

procedure TProyecto.doCancelar;
begin
  FLoading := True;
  try
    if rsDet.State in dsEditModes then
      rsDet.Cancel();
    if Proyecto.State in dsEditModes then
      Proyecto.Cancel();

    rsDet.CancelBatch();
    proyecto.CancelBatch();

    browsebotonstate();
  finally
    FLoading := False;
  end;
end;

procedure TProyecto.doEditar;
begin
  Proyecto.Edit();
  Editbotonstate();
end;

procedure TProyecto.doGuardar;
begin
  FLoading := True;
  try
    if proyecto.State in dsEditModes then
      Proyecto.Post();

    if rsDet.State in dsEditModes then
      rsDet.Post();

    Proyecto.UpdateBatch(arAll);
    rsDet.UpdateBatch(arAll);

    ActualizarCC();
    browsebotonstate();
  finally
    FLoading := False;
  end;
end;

procedure TProyecto.doNuevo;
begin
  Proyecto.Append();
  Newbotonstate();
end;

procedure TProyecto.doPrint;
begin
  // nothing for now
end;

procedure TProyecto.browsebotonstate;
begin
    ANuevo.enabled      := dm.TienePermisoShow(pAgregar, permisos);
    if ((CampodeCierre <> '') and (ds.DataSet.FieldByName(CampodeCierre).Value <= dm.Cierre)) then
      AEditar.enabled     := false
    else
      AEditar.enabled     := (not(ds.dataset.IsEmpty) and  (dm.TienePermisoShow(pEditar, permisos))); //(Peditar and not(ds.dataset.IsEmpty)) ;

    AGuardar.enabled    := False;
    ACancelar.enabled   := False;

    if ((CampodeCierre <> '') and (ds.DataSet.FieldByName(CampodeCierre).Value <= dm.Cierre)) then
      ABorrar.Enabled     := False
    else
      ABorrar.Enabled     := (not(ds.dataset.IsEmpty)) and (not(ds.dataset.IsEmpty) and (dm.TienePermisoShow(pBorrar,permisos))); //(Pborrar and not(ds.dataset.IsEmpty)) ;

    Asalir.Enabled      := True;
    ALocalizar.Enabled  := True;
    Aprint.Enabled      := (not(ds.dataset.IsEmpty)) and (dm.TienePermisoShow(pImprimir,Permisos));
    AAprobacion.enabled := (not(ds.dataset.IsEmpty)) and (dm.TienePermisoShow(pAprobar,Permisos));

    if ((CampodeCierre <> '') and (ds.DataSet.FieldByName(CampodeCierre).Value <= dm.Cierre)) then
      AAnular.Enabled     := False
    else
      AAnular.enabled     := (not(ds.dataset.IsEmpty)) and (dm.TienePermisoShow(pAnular,Permisos));

    cxGrid1.Enabled := False;
    ds.AutoEdit := False;
    dsProyectoPartida.AutoEdit := False;
    DBTreeList.Enabled := True;
end;

procedure TProyecto.Editbotonstate;
begin
  ANuevo.enabled := False;
  AEditar.enabled := False;
  AGuardar.enabled := True;
  ACancelar.enabled := True;
  ABorrar.Enabled := False;
  Asalir.Enabled := false;
  ALocalizar.Enabled := False;
  Aprint.Enabled := false;
  AAprobacion.enabled := false;
  AAnular.enabled := false;

  cxGrid1.Enabled := True;
  ds.AutoEdit := True;
  dsProyectoPartida.AutoEdit := True;
  DBTreeList.Enabled := False;
end;

procedure TProyecto.Newbotonstate;
begin
  ANuevo.enabled := False;
  AEditar.enabled := False;
  AGuardar.enabled := True;
  ACancelar.enabled := True;
  ABorrar.Enabled := False;
  Asalir.Enabled := false;
  ALocalizar.Enabled := False;
  Aprint.Enabled := false;
  AAprobacion.enabled := false;
  AAnular.enabled := false;

  cxGrid1.Enabled := True ;
  ds.AutoEdit := True;
  dsProyectoPartida.AutoEdit := True;
  DBTreeList.Enabled := False;
end;
procedure TProyecto.ANuevoExecute(Sender: TObject);
begin
  inherited;
  doNuevo();
end;

procedure TProyecto.AEditarExecute(Sender: TObject);
begin
  inherited;
  doEditar();
end;

procedure TProyecto.AGuardarExecute(Sender: TObject);
begin
  inherited;
  doGuardar();
end;

procedure TProyecto.ACancelarExecute(Sender: TObject);
begin
  inherited;
  doCancelar();
end;

procedure TProyecto.ABorrarExecute(Sender: TObject);
begin
  inherited;
  doBorrar();
end;

procedure TProyecto.AsalirExecute(Sender: TObject);
begin
  inherited;
  Close();
end;

procedure TProyecto.AprintExecute(Sender: TObject);
begin
  inherited;
  doPrint();
end;

procedure TProyecto.rsDetidPartidaValidate(Sender: TField);
begin
  inherited;
  if Partida.Locate('idPartida',rsDetIdPartida.Value,[]) then begin
    rsDetIdUnidad.Value := PartidaIdUnidad.Value;
    rsDetCostoUnidad.Value := PartidaCostoUnidad.AsCurrency;
  end;
end;

end.
