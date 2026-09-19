unit uArbolProyectos;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms, 
  Dialogs, cxControls, cxContainer, cxTreeView, DB, ADODB, Comctrls,
  ImgList;

const
  NO_PROJECT : TGUID = '{04FF19F7-A400-4DB0-93DB-C1ECECF79FD2}';

type
  TTreeKey = class
  private
    FIdProyecto: TGUID;
  public
    property idProyecto: TGUID read FIdProyecto write FidProyecto;
    constructor Create(const id: TGUID);
  end;

  TSelectedEvent = procedure (const idProy: TGUID) of object;
  
type
  TArbolProyectos = class(TFrame)
    Tree: TcxTreeView;
    rsProyecto: TADODataSet;
    rsProyectoidProyecto: TGuidField;
    rsProyectoidProyectoParent: TGuidField;
    rsProyectoProyecto: TStringField;
    rsProyectoProyectoDesc: TStringField;
    rsProyectoStatus: TSmallintField;
    rsProyectoUbicacion: TStringField;
    rsProyectoInicio: TDateTimeField;
    rsProyectoFin: TDateTimeField;
    rsProyectoNotas: TStringField;
    rsProyectoOTData: TStringField;
    rsProyectoActivo: TBooleanField;
    rsProyectoNivel: TSmallintField;
    rsProyectoidUnidad: TStringField;
    rsProyectoCantidad: TFloatField;
    ImageList1: TImageList;
    stateImgs: TImageList;
    procedure TreeChange(Sender: TObject; Node: TTreeNode);
    procedure TreeGetImageIndex(Sender: TObject; Node: TTreeNode);
  private
    FOnSelectedChange: TSelectedEvent;
    function FindById(const pid: TGUID): TTreeNode;
    function GetSelectedNode: TTreeKey;
    function GetKeyActual: TGUID;
    procedure SetKeyActual(const Value: TGUID);
    { Private declarations }
  public
    { Public declarations }
    procedure FillTree(const msk: string = '%');
    procedure ClearTree;
    destructor Destroy; override;
    property OnSelectedChange: TSelectedEvent read FOnSelectedChange write FOnSelectedChange;
    property NodoActual: TTreeKey read GetSelectedNode;
    property KeyActual: TGUID read GetKeyActual write SetKeyActual;
  end;

implementation

uses UCSMainForm, Udata;

{$R *.dfm}

{ TArbolProyectos }

procedure TArbolProyectos.ClearTree;
var
  j: integer;
  key: TTreeKey;
begin
  for j := 0 to Tree.Items.Count - 1 do begin
    if Tree.Items[j].Data <> nil then begin
      Key := (Tree.Items[j].Data); // as TTreeKey);
      FreeAndNil(Key);
    end;
  end;
  Tree.Items.Clear();
end;

destructor TArbolProyectos.Destroy;
begin
  ClearTree();
  inherited;
end;

procedure TArbolProyectos.FillTree(const msk: string);
var
  //Key: TTreeKey;
  Node: TTreeNode;
begin
  ClearTree();
  if msk <> '' then begin
    with rsProyecto do begin
      if Active then
        Close();
      Parameters[1].Value := msk;
      Open();
      while not Eof do begin
        if rsProyectoIdProyectoParent.IsNull then
          Tree.Items.AddObject(nil, rsProyectoProyectoDesc.Value, TTreeKey.Create(rsProyectoIdProyecto.AsGuid))
        else begin
          Node := FindByid(rsProyectoIdProyectoParent.AsGuid);
          if Node <> nil then
            Tree.Items.AddChildObject(Node,rsProyectoProyectoDesc.Value, TTreeKey.Create(rsProyectoIdProyecto.AsGuid));
        end;
        Next();
      end;
      Close();
    end;
  end;
  Tree.FullExpand();
end;

function TArbolProyectos.FindById(const pid: TGUID): TTreeNode;
var
  j: Integer;
  akey: TTreeKey;
begin
  Result := nil;
  for j := 0 to Tree.Items.Count - 1 do begin
    if (Tree.Items[j].Data <> nil) then begin
      akey := TTreeKey(Tree.Items[j].Data);
      if not (GuidToString(akey.IdProyecto) <> GuidToString(pid)) then begin
        Result := Tree.Items[j];
        break;
      end;
    end;
  end;
end;

{ TTreeKey }

constructor TTreeKey.Create(const id: TGUID);
begin
  Inherited Create();
  FidProyecto := id;
end;

function TArbolProyectos.GetKeyActual: TGUID;
var
  Key: TTreeKey;
begin
  Key := NodoActual;
  if Key <> nil then
    Result := Key.idProyecto
  else
    Result := NO_PROJECT;
end;

function TArbolProyectos.GetSelectedNode: TTreeKey;
begin
  //if Tree.Selected.Data <> nil then
  if Tree.Selected = nil then
    Result := nil
  else
    Result := Tree.Selected.Data;
end;

procedure TArbolProyectos.SetKeyActual(const Value: TGUID);
var
  Node: TTreeNode;
begin
  Node := FindById(Value);
  if Node <> nil then
    Node.Selected := True;
end;


procedure TArbolProyectos.TreeChange(Sender: TObject; Node: TTreeNode);
begin
  if Assigned(FOnSelectedChange) then begin
    if Node.Data = nil then
      FOnSelectedChange(NO_PROJECT)
    else
      FOnSelectedChange(TTreeKey(Node.Data).idProyecto);
  end;
end;

procedure TArbolProyectos.TreeGetImageIndex(Sender: TObject;
  Node: TTreeNode);
begin
  if Node.Selected then begin
    Node.ImageIndex := 0 ;
  end
  else begin
    if Node.HasChildren then
      Node.ImageIndex := 2
    else
      Node.ImageIndex := 1;
  end;
end;

end.
