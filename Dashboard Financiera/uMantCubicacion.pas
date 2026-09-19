unit uMantCubicacion;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, uform, DB, Wwdatsrc, uArbolProyectos, dxExEdtr, ADODB, dxDBTLCl,
  dxGrClms, cxDBEdit, cxLookupEdit, cxDBLookupEdit, cxDBLookupComboBox,
  cxContainer, cxEdit, cxTextEdit, cxMaskEdit, cxDropDownEdit,
  cxImageComboBox, dxEditor, dxEdLib, dxDBELib, dxDBCtrl, dxDBGrid, dxTL,
  dxCntner, ExtCtrls, DBCtrls, StdCtrls, cxPC, cxControls, ufrArbol;

type
  TMantCubicacion = class(TFForm)
    PageControl1: TcxPageControl;
    TabSheet1: TcxTabSheet;
    Label1: TLabel;
    Label5: TLabel;
    eproy: TdxDBEdit;
    dxDBEdit2: TdxDBEdit;
    TabSheet2: TcxTabSheet;
    dxDBGrid2: TdxDBGrid;
    dxDBGrid2idCentroCostoGasto: TdxDBGridColumn;
    dxDBGrid2idCentroCosto: TdxDBGridColumn;
    dxDBGrid2Fecha: TdxDBGridDateColumn;
    dxDBGrid2Cantidad: TdxDBGridMaskColumn;
    dxDBGrid2Gasto: TdxDBGridCurrencyColumn;
    dxDBGrid2CentroCostoGasto: TdxDBGridMaskColumn;
    dxDBGrid2idPartida: TdxDBGridMaskColumn;
    dxDBGrid2idDocumento: TdxDBGridColumn;
    dxDBGrid2Referencia: TdxDBGridMaskColumn;
    dxDBGrid2idTipoDoc: TdxDBGridMaskColumn;
    dxDBGrid2idUnidad: TdxDBGridMaskColumn;
    dxDBGrid2Notas: TdxDBGridMaskColumn;
    rs: TADODataSet;
    frArbol1: TfrArbol;
    procedure FormCreate(Sender: TObject);
  private
    { Private declarations }
    procedure ActualizarProyecto(const Key: Variant);
  public
    { Public declarations }
  end;

var
  MantCubicacion: TMantCubicacion;

implementation

{$R *.dfm}

procedure TMantCubicacion.ActualizarProyecto(const Key: Variant);
begin
  with rs do begin
    Close();
    if Key <> NULL then begin
      Parameters[1].Value := Key;
      Open();
    end;
  end;
end;

procedure TMantCubicacion.FormCreate(Sender: TObject);
begin
  inherited;
  frArbol1.CommandName := 'CostCentroCostoTree';
  //frArbol1.KeyField := 'Key';
  //frArbol1.NameField := 'NameField';
  //frArbol1.ParentKeyField := 'ParentKey';
  frArbol1.FillTree(NULL);
  frArbol1.OnSelectedChange := ActualizarProyecto;
  frArbol1.Tree.FullExpand();
end;

end.
