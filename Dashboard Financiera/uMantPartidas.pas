unit uMantPartidas;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, uMantClassRS, cxLookAndFeelPainters, DB, ADODB, ImgList,
  ActnList, Wwdatsrc, StdCtrls, cxButtons, Gradient, cxStyles,
  cxCustomData, cxGraphics, cxFilter, cxData, cxDataStorage, cxEdit,
  cxDBData, cxGridCustomTableView, cxGridTableView, cxGridDBTableView,
  cxGridLevel, cxClasses, cxControls, cxGridCustomView, cxGrid,
  cxDBLookupComboBox;

type
  TMantPartidas = class(TMantClassRS)
    rs: TADODataSet;
    rsidPartida: TStringField;
    rsPartida: TStringField;
    rsidUnidad: TStringField;
    cxGrid1DBTableView1: TcxGridDBTableView;
    cxGrid1Level1: TcxGridLevel;
    cxGrid1: TcxGrid;
    cxGrid1DBTableView1idPartida: TcxGridDBColumn;
    cxGrid1DBTableView1Partida: TcxGridDBColumn;
    cxGrid1DBTableView1idUnidad: TcxGridDBColumn;
    rsUnidad: TADODataSet;
    rsUnidadidUnidad: TStringField;
    rsUnidadUnidad: TStringField;
    rsUnidadidUnidadBase: TStringField;
    rsUnidadidFactor: TFloatField;
    rsUnidadUidUnidad: TGuidField;
    dsUnidad: TDataSource;
    rsCostoUnidad: TBCDField;
    procedure FormCreate(Sender: TObject);
    procedure rsNewRecord(DataSet: TDataSet);
  private
    { Private declarations }
  public
    { Public declarations }
  end;

var
  MantPartidas: TMantPartidas;

implementation

uses Udata;

{$R *.dfm}

procedure TMantPartidas.FormCreate(Sender: TObject);
begin
  inherited;
  rsUnidad.Open();
end;

procedure TMantPartidas.rsNewRecord(DataSet: TDataSet);
begin
  inherited;
  rsCostoUnidad.Value := 0;
end;

end.
