inherited MantCubicacion: TMantCubicacion
  Left = 332
  Top = 194
  Caption = 'Cubicaciones'
  ClientHeight = 509
  ClientWidth = 792
  Font.Name = 'Tahoma'
  PixelsPerInch = 96
  TextHeight = 13
  object PageControl1: TcxPageControl [0]
    Left = 319
    Top = 0
    Width = 473
    Height = 509
    ActivePage = TabSheet1
    Align = alRight
    LookAndFeel.NativeStyle = True
    TabOrder = 0
    ClientRectBottom = 505
    ClientRectLeft = 2
    ClientRectRight = 469
    ClientRectTop = 22
    object TabSheet1: TcxTabSheet
      Caption = 'Datos del GFH'
      object Label1: TLabel
        Left = 8
        Top = 12
        Width = 43
        Height = 13
        Caption = 'Proyecto'
      end
      object Label5: TLabel
        Left = 8
        Top = 38
        Width = 35
        Height = 13
        Caption = 'Descrip'
      end
      object eproy: TdxDBEdit
        Left = 64
        Top = 8
        Width = 121
        TabOrder = 0
        DataField = 'Proyecto'
        DataSource = DS
        StyleController = dm.dxEstilo
      end
      object dxDBEdit2: TdxDBEdit
        Left = 64
        Top = 32
        Width = 314
        TabOrder = 1
        AutoSize = False
        DataField = 'ProyectoDesc'
        DataSource = DS
        StyleController = dm.dxEstilo
        Height = 29
      end
    end
    object TabSheet2: TcxTabSheet
      Caption = 'Gastos del Proyecto'
      ImageIndex = 1
      object dxDBGrid2: TdxDBGrid
        Left = 0
        Top = 0
        Width = 467
        Height = 483
        Bands = <
          item
          end>
        DefaultLayout = True
        HeaderPanelRowCount = 1
        KeyField = 'idCentroCostoGasto'
        ShowGroupPanel = True
        ShowSummaryFooter = True
        SummaryGroups = <
          item
            DefaultGroup = True
            SummaryItems = <
              item
                ColumnName = 'dxDBGrid2idPartida'
                SummaryField = 'Gasto'
                SummaryFormat = '(#,0.00)'
                SummaryType = cstSum
              end>
            Name = 'Partida'
          end>
        SummarySeparator = ', '
        Align = alClient
        TabOrder = 0
        Filter.Active = True
        Filter.Criteria = {00000000}
        OptionsDB = [edgoCancelOnExit, edgoCanDelete, edgoCanInsert, edgoCanNavigation, edgoConfirmDelete, edgoLoadAllRecords, edgoUseBookmarks]
        object dxDBGrid2idCentroCostoGasto: TdxDBGridColumn
          Visible = False
          Width = 37
          BandIndex = 0
          RowIndex = 0
          FieldName = 'idCentroCostoGasto'
        end
        object dxDBGrid2idCentroCosto: TdxDBGridColumn
          Visible = False
          Width = 37
          BandIndex = 0
          RowIndex = 0
          FieldName = 'idCentroCosto'
        end
        object dxDBGrid2Fecha: TdxDBGridDateColumn
          Width = 67
          BandIndex = 0
          RowIndex = 0
          FieldName = 'Fecha'
        end
        object dxDBGrid2Cantidad: TdxDBGridMaskColumn
          Width = 37
          BandIndex = 0
          RowIndex = 0
          FieldName = 'Cantidad'
        end
        object dxDBGrid2Gasto: TdxDBGridCurrencyColumn
          Width = 61
          BandIndex = 0
          RowIndex = 0
          FieldName = 'Gasto'
          SummaryFooterType = cstSum
          SummaryFooterField = 'Gasto'
          SummaryFooterFormat = '#,0.00'
          Nullable = False
        end
        object dxDBGrid2CentroCostoGasto: TdxDBGridMaskColumn
          Width = 103
          BandIndex = 0
          RowIndex = 0
          FieldName = 'CentroCostoGasto'
        end
        object dxDBGrid2idPartida: TdxDBGridMaskColumn
          Sorted = csUp
          Visible = False
          Width = 49
          BandIndex = 0
          RowIndex = 0
          FieldName = 'idPartida'
          GroupIndex = 0
        end
        object dxDBGrid2idDocumento: TdxDBGridColumn
          Visible = False
          Width = 37
          BandIndex = 0
          RowIndex = 0
          FieldName = 'idDocumento'
        end
        object dxDBGrid2Referencia: TdxDBGridMaskColumn
          Width = 61
          BandIndex = 0
          RowIndex = 0
          FieldName = 'Referencia'
        end
        object dxDBGrid2idTipoDoc: TdxDBGridMaskColumn
          BandIndex = 0
          RowIndex = 0
          FieldName = 'idTipoDoc'
        end
        object dxDBGrid2idUnidad: TdxDBGridMaskColumn
          Width = 48
          BandIndex = 0
          RowIndex = 0
          FieldName = 'idUnidad'
        end
        object dxDBGrid2Notas: TdxDBGridMaskColumn
          Width = 98
          BandIndex = 0
          RowIndex = 0
          FieldName = 'Notas'
        end
      end
    end
  end
  inline frArbol1: TfrArbol [1]
    Left = 0
    Top = 0
    Width = 317
    Height = 509
    Align = alLeft
    TabOrder = 1
    inherited Tree: TcxTreeView
      Width = 317
      Height = 509
    end
  end
  inherited DS: TwwDataSource
    DataSet = rs
    Left = 123
    Top = 117
  end
  object rs: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    CommandText = 'ProyProyectoAct;1'
    CommandType = cmdStoredProc
    Parameters = <
      item
        Name = '@RETURN_VALUE'
        DataType = ftInteger
        Direction = pdReturnValue
        Precision = 10
        Value = 0
      end
      item
        Name = '@idProyecto'
        Attributes = [paNullable]
        DataType = ftGuid
        Value = Null
      end>
    Left = 646
    Top = 192
  end
end
