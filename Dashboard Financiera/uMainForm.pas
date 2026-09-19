unit uMainForm;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, dxNavBarCollns, dxNavBarBase, ExtCtrls, dxNavBar, ActnList,
  jpeg, cxControls, cxContainer, cxEdit, cxImage, Gradient, cxLabel,
  ToolWin, ActnMan, ActnCtrls, ActnMenus, XPStyleActnCtrls, ActnColorMaps,
  dxNavBarStyles, XPMan;

type
  TMainForm = class(TForm)
    dxNavBar1: TdxNavBar;
    dxNavBar1Group1: TdxNavBarGroup;
    dxNavBar1Group2: TdxNavBarGroup;
    dxNavBar1Group3: TdxNavBarGroup;
    dxNavBar1Group4: TdxNavBarGroup;
    biSalir: TdxNavBarItem;
    aClose: TAction;
    Gradient1: TGradient;
    cxLabel1: TcxLabel;
    ActionMainMenuBar1: TActionMainMenuBar;
    Acciones: TActionManager;
    XPColorMap1: TXPColorMap;
    Action1: TAction;
    Action2: TAction;
    biCentroCosto: TdxNavBarItem;
    biPartidas: TdxNavBarItem;
    biProyecto: TdxNavBarItem;
    biPresupuesto: TdxNavBarItem;
    biLogOf: TdxNavBarItem;
    Proyecto: TAction;
    CentroCosto: TAction;
    MantPresupuesto: TAction;
    MantPartidas: TAction;
    Password: TAction;
    Unidad: TAction;
    Selempresa: TAction;
    XPManifest1: TXPManifest;
    procedure aCloseExecute(Sender: TObject);
    procedure Action1Execute(Sender: TObject);
    procedure Action2Execute(Sender: TObject);
    procedure FormCreate(Sender: TObject);
    procedure ProyectoExecute(Sender: TObject);
    procedure MantPartidasExecute(Sender: TObject);
    procedure MantPresupuestoExecute(Sender: TObject);
    procedure CentroCostoExecute(Sender: TObject);
    procedure PasswordExecute(Sender: TObject);
    procedure UnidadExecute(Sender: TObject);
    procedure SelEmpresaExecute(Sender: TObject);    
  private
    procedure RefrescarAcciones;
    { Private declarations }
  public
    { Public declarations }
  end;

var
  MainForm: TMainForm;

implementation

uses UUtiles, Udata, USeguridad, uSetup, uCentroCosto,
  uMantPartidas, uMantPresupuesto, uProyecto, uUnidad, uMantCubicacion,
  uDistribuirCosto, udmRepository, uMultiLogin, uSelEmpresa;

{$R *.dfm}

procedure TMainForm.aCloseExecute(Sender: TObject);
begin
  Close();
end;

procedure TMainForm.Action1Execute(Sender: TObject);
begin
  ModalShow(TSetup);
end;

procedure TMainForm.Action2Execute(Sender: TObject);
begin
  ModalShow(TSeguridad);
end;

procedure TMainForm.FormCreate(Sender: TObject);
var
  conStr: string;
begin
  ModalShow(tMultiLogin);
  conStr := BuscarConStrEmpresa(dm.UsuarioActual,True);
  if ConStr <> '' then begin
    dm.AbrirCompania(conStr);
    RefrescarAcciones();
  end;
end;

procedure TMainForm.ProyectoExecute(Sender: TObject);
begin
  ModalShow(TProyecto)
end;

procedure TMainForm.MantPartidasExecute(Sender: TObject);
begin
  ModalShow(TMantPartidas);
end;

procedure TMainForm.MantPresupuestoExecute(Sender: TObject);
begin
  ModalShow(TMantPresupuesto);
end;

procedure TMainForm.CentroCostoExecute(Sender: TObject);
begin
  ModalShow(TCentroCosto)
end;

procedure TMainForm.PasswordExecute(Sender: TObject);
begin
   inherited;
   ModalShow(tMultiLogin);
   SelEmpresaExecute(nil);
end;

procedure TMainForm.RefrescarAcciones;
Var
  i : Integer;
begin
   for i := 0 to acciones.ActionCount - 1 do begin
      if TAction(acciones.Actions[i]).Tag <> 5 then //las acciones de salir y logoff no deben verificar seguridad
      TAction(acciones.Actions[i]).enabled := (dm.TienepermisoShow(pAbrir,(dm.apppermisos(acciones.Actions[i].name))));
   end;
   cxLabel1.Caption := Format('Proyectos - [%s]',[dm.ConfiguracionCompania.Asstring]);
end;

procedure TMainForm.UnidadExecute(Sender: TObject);
begin
  ModalShow(TUnidad);
end;

procedure TMainForm.SelEmpresaExecute(Sender: TObject);
Var
  ConexionStr : String;
begin
  ConexionStr := BuscarConStrEmpresa(dmRepository.UsuarioActual);
  if ConexionStr <> '' then begin
    dm.AbrirCompania(ConexionStr);
    RefrescarAcciones();
  end;
end;

end.
