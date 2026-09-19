inherited MantPartidas: TMantPartidas
  Left = 274
  Top = 116
  Caption = 'Partidas de presupuesto'
  ClientHeight = 332
  ClientWidth = 509
  PixelsPerInch = 96
  TextHeight = 13
  inherited Gradient1: TGradient
    Width = 509
  end
  inherited Gradient2: TGradient
    Width = 509
  end
  inherited btImprimir: TcxButton
    Top = 277
    Width = 56
    Height = 50
  end
  inherited btLocalizar: TcxButton
    Top = 277
    Width = 56
    Height = 50
  end
  inherited btNuevo: TcxButton
    Top = 277
    Width = 56
    Height = 50
  end
  inherited btCancelar: TcxButton
    Top = 277
    Width = 56
    Height = 50
  end
  inherited btGuardar: TcxButton
    Top = 277
    Width = 56
    Height = 50
  end
  inherited btBorrar: TcxButton
    Left = 367
    Top = 277
    Width = 56
    Height = 50
  end
  inherited btSalir: TcxButton
    Left = 448
    Top = 277
    Width = 56
    Height = 50
  end
  inherited btEditar: TcxButton
    Top = 277
    Width = 56
    Height = 50
  end
  object cxGrid1: TcxGrid [10]
    Left = 2
    Top = 36
    Width = 505
    Height = 233
    Anchors = [akLeft, akTop, akRight, akBottom]
    TabOrder = 8
    LookAndFeel.NativeStyle = True
    object cxGrid1DBTableView1: TcxGridDBTableView
      DataController.DataSource = DS
      DataController.Summary.DefaultGroupSummaryItems = <>
      DataController.Summary.FooterSummaryItems = <>
      DataController.Summary.SummaryGroups = <>
      NavigatorButtons.ConfirmDelete = False
      OptionsView.GroupByBox = False
      object cxGrid1DBTableView1idPartida: TcxGridDBColumn
        Caption = 'Codigo'
        DataBinding.FieldName = 'idPartida'
        Options.Filtering = False
      end
      object cxGrid1DBTableView1Partida: TcxGridDBColumn
        DataBinding.FieldName = 'Partida'
        Options.Filtering = False
        Width = 271
      end
      object cxGrid1DBTableView1idUnidad: TcxGridDBColumn
        Caption = 'Unidad'
        DataBinding.FieldName = 'idUnidad'
        PropertiesClassName = 'TcxLookupComboBoxProperties'
        Properties.ImmediatePost = True
        Properties.KeyFieldNames = 'idUnidad'
        Properties.ListColumns = <
          item
            FieldName = 'Unidad'
          end>
        Properties.ListOptions.CaseInsensitive = True
        Properties.ListOptions.GridLines = glNone
        Properties.ListOptions.ShowHeader = False
        Properties.ListSource = dsUnidad
        Options.Filtering = False
        Width = 87
      end
    end
    object cxGrid1Level1: TcxGridLevel
      GridView = cxGrid1DBTableView1
    end
  end
  inherited DS: TwwDataSource
    DataSet = rs
  end
  inherited ImageList: TImageList
    Left = 334
    Top = 128
  end
  object rs: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    OnNewRecord = rsNewRecord
    CommandText = 'ProyrsPartida'
    CommandType = cmdStoredProc
    Parameters = <>
    Left = 384
    Top = 104
    object rsidPartida: TStringField
      FieldName = 'idPartida'
      Size = 16
    end
    object rsPartida: TStringField
      FieldName = 'Partida'
      Size = 100
    end
    object rsidUnidad: TStringField
      FieldName = 'idUnidad'
      Size = 16
    end
    object rsCostoUnidad: TBCDField
      FieldName = 'CostoUnidad'
      Precision = 19
      Size = 2
    end
  end
  object rsUnidad: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    LockType = ltReadOnly
    CommandText = 'svRSUnidad;1'
    CommandType = cmdStoredProc
    Parameters = <>
    Left = 90
    Top = 126
    object rsUnidadidUnidad: TStringField
      FieldName = 'idUnidad'
      Size = 16
    end
    object rsUnidadUnidad: TStringField
      FieldName = 'Unidad'
      Size = 50
    end
    object rsUnidadidUnidadBase: TStringField
      FieldName = 'idUnidadBase'
      Size = 50
    end
    object rsUnidadidFactor: TFloatField
      FieldName = 'idFactor'
    end
    object rsUnidadUidUnidad: TGuidField
      FieldName = 'UidUnidad'
      FixedChar = True
      Size = 38
    end
  end
  object dsUnidad: TDataSource
    DataSet = rsUnidad
    Left = 204
    Top = 116
  end
end
