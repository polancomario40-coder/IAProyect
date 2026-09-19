object MainForm: TMainForm
  Left = 361
  Top = 178
  Width = 653
  Height = 497
  Caption = 'Proyectos'
  Color = 16382969
  Constraints.MinHeight = 397
  Constraints.MinWidth = 538
  Font.Charset = DEFAULT_CHARSET
  Font.Color = clWindowText
  Font.Height = -11
  Font.Name = 'MS Sans Serif'
  Font.Style = []
  OldCreateOrder = False
  Position = poDesktopCenter
  OnCreate = FormCreate
  DesignSize = (
    645
    463)
  PixelsPerInch = 96
  TextHeight = 13
  object Gradient1: TGradient
    Left = 188
    Top = 24
    Width = 457
    Height = 439
    Align = alClient
    ColorEnd = clSilver
    Reverse = True
    Style = gsLinearV
  end
  object dxNavBar1: TdxNavBar
    Left = 0
    Top = 24
    Width = 188
    Height = 439
    Align = alLeft
    ActiveGroupIndex = 0
    DragCopyCursor = -1119
    DragCursor = -1120
    DragDropFlags = [fAllowDragLink, fAllowDropLink, fAllowDragGroup, fAllowDropGroup]
    HotTrackedGroupCursor = crDefault
    HotTrackedLinkCursor = -1118
    View = 8
    object dxNavBar1Group1: TdxNavBarGroup
      Caption = 'Tablas'
      LinksUseSmallImages = True
      SelectedLinkIndex = -1
      ShowAsIconView = False
      ShowControl = False
      TopVisibleLinkIndex = 0
      UseControl = False
      UseSmallImages = True
      Visible = True
      Links = <
        item
          Item = biProyecto
        end
        item
          Item = biPresupuesto
        end
        item
          Item = biCentroCosto
        end>
    end
    object dxNavBar1Group2: TdxNavBarGroup
      Caption = 'Operaciones'
      LinksUseSmallImages = True
      SelectedLinkIndex = -1
      ShowAsIconView = False
      ShowControl = False
      TopVisibleLinkIndex = 0
      UseControl = False
      UseSmallImages = True
      Visible = True
      Links = <>
    end
    object dxNavBar1Group3: TdxNavBarGroup
      Caption = 'Reportes'
      Expanded = False
      LinksUseSmallImages = True
      SelectedLinkIndex = -1
      ShowAsIconView = False
      ShowControl = False
      TopVisibleLinkIndex = 0
      UseControl = False
      UseSmallImages = True
      Visible = True
      Links = <>
    end
    object dxNavBar1Group4: TdxNavBarGroup
      Caption = 'Otros'
      LinksUseSmallImages = True
      SelectedLinkIndex = -1
      ShowAsIconView = False
      ShowControl = False
      TopVisibleLinkIndex = 0
      UseControl = False
      UseSmallImages = True
      Visible = True
      Links = <
        item
          Item = biLogOf
        end
        item
          Item = biSalir
        end>
    end
    object biSalir: TdxNavBarItem
      Action = aClose
    end
    object biCentroCosto: TdxNavBarItem
      Action = CentroCosto
    end
    object biPartidas: TdxNavBarItem
      Action = MantPartidas
    end
    object biProyecto: TdxNavBarItem
      Action = Proyecto
    end
    object biPresupuesto: TdxNavBarItem
      Action = MantPresupuesto
    end
    object biLogOf: TdxNavBarItem
      Action = Password
    end
  end
  object cxLabel1: TcxLabel
    Left = 216
    Top = 354
    Width = 421
    Height = 105
    Anchors = [akRight, akBottom]
    AutoSize = False
    Caption = 'Proyectos'
    ParentColor = False
    ParentFont = False
    Properties.Alignment.Horz = taRightJustify
    Properties.Alignment.Vert = taBottomJustify
    Properties.ShadowedColor = clNone
    Properties.Transparent = True
    Properties.WordWrap = True
    Style.Color = clSilver
    Style.Font.Charset = DEFAULT_CHARSET
    Style.Font.Color = clActiveCaption
    Style.Font.Height = -19
    Style.Font.Name = 'Tahoma'
    Style.Font.Style = [fsBold]
    Style.LookAndFeel.NativeStyle = True
    Style.TextColor = clSilver
  end
  object ActionMainMenuBar1: TActionMainMenuBar
    Left = 0
    Top = 0
    Width = 645
    Height = 24
    UseSystemFont = False
    ActionManager = Acciones
    Caption = 'ActionMainMenuBar1'
    ColorMap = XPColorMap1
    Font.Charset = DEFAULT_CHARSET
    Font.Color = clWindowText
    Font.Height = -11
    Font.Name = 'Tahoma'
    Font.Style = []
    Spacing = 0
  end
  object Acciones: TActionManager
    ActionBars = <
      item
        Items = <
          item
            Items = <
              item
                Action = Proyecto
                Caption = '&Proyectos'
              end
              item
                Action = CentroCosto
                Caption = '&Centros de costo'
              end
              item
                Caption = '-'
              end
              item
                Action = Password
                Caption = '&Log off'
              end
              item
                Action = aClose
                Caption = '&Salir'
              end>
            Caption = '&Tablas'
          end
          item
            Items = <
              item
                Action = MantPresupuesto
              end>
            Caption = '&Operaciones'
          end
          item
            Items = <
              item
                Caption = '-'
              end>
            Caption = 'R&eportes'
          end
          item
            Items = <
              item
                Action = Action1
                Caption = '&Compa'#241'ia'
              end
              item
                Action = Action2
                Caption = '&Usuarios'
              end
              item
                Caption = '-'
              end
              item
                Action = Unidad
                Caption = 'U&nidades de medida'
              end
              item
                Action = MantPartidas
                Caption = 'P&artidas de presupuesto'
              end>
            Caption = '&Configuracion'
          end>
        ActionBar = ActionMainMenuBar1
      end>
    Left = 374
    Top = 140
    StyleName = 'XP Style'
    object aClose: TAction
      Category = 'Salir'
      Caption = 'Salir'
      OnExecute = aCloseExecute
    end
    object Action1: TAction
      Category = 'Configuracion'
      Caption = 'Compa'#241'ia'
      OnExecute = Action1Execute
    end
    object Action2: TAction
      Category = 'Configuracion'
      Caption = 'Usuarios'
      OnExecute = Action2Execute
    end
    object Proyecto: TAction
      Category = 'Tablas'
      Caption = 'Proyectos'
      OnExecute = ProyectoExecute
    end
    object CentroCosto: TAction
      Category = 'Tablas'
      Caption = 'Centros de costo'
      OnExecute = CentroCostoExecute
    end
    object MantPresupuesto: TAction
      Category = 'Operaciones'
      Caption = 'Presupuestos'
      OnExecute = MantPresupuestoExecute
    end
    object MantPartidas: TAction
      Category = 'Tablas'
      Caption = 'Partidas de presupuesto'
      OnExecute = MantPartidasExecute
    end
    object Password: TAction
      Category = 'Salir'
      Caption = 'Log off'
      OnExecute = PasswordExecute
    end
    object Unidad: TAction
      Category = 'Configuracion'
      Caption = 'Unidades de medida'
      OnExecute = UnidadExecute
    end
    object Selempresa: TAction
      Tag = 5
      Category = 'Salir'
      Caption = 'Seleccionar empresa'
      OnExecute = SelempresaExecute
    end
  end
  object XPColorMap1: TXPColorMap
    HighlightColor = 15660791
    BtnSelectedColor = clBtnFace
    UnusedColor = 15660791
    Left = 232
    Top = 88
  end
  object XPManifest1: TXPManifest
    Left = 312
    Top = 234
  end
end
