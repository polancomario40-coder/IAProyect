inherited MantPresupuesto: TMantPresupuesto
  Left = 392
  Top = 182
  Caption = 'Registrar presupuesto'
  ClientHeight = 456
  ClientWidth = 784
  OldCreateOrder = True
  PixelsPerInch = 96
  TextHeight = 13
  inherited Gradient1: TGradient
    Width = 784
  end
  inherited Gradient2: TGradient
    Width = 784
  end
  object Label1: TLabel [2]
    Left = 12
    Top = 40
    Width = 58
    Height = 13
    Caption = 'Prespuesto:'
  end
  object Label2: TLabel [3]
    Left = 12
    Top = 64
    Width = 47
    Height = 13
    Caption = 'Proyecto:'
  end
  object Label3: TLabel [4]
    Left = 464
    Top = 66
    Width = 52
    Height = 13
    Caption = 'Tipo Pres.:'
  end
  inherited btImprimir: TcxButton
    Top = 409
    Action = Aprint
  end
  inherited btLocalizar: TcxButton
    Top = 409
  end
  inherited btNuevo: TcxButton
    Top = 409
  end
  inherited btCancelar: TcxButton
    Top = 409
  end
  inherited btGuardar: TcxButton
    Top = 409
  end
  inherited btBorrar: TcxButton
    Left = 645
    Top = 409
  end
  inherited btSalir: TcxButton
    Left = 728
    Top = 409
  end
  inline ArbolProyectos1: TArbolProyectos [12]
    Left = 4
    Top = 89
    Width = 279
    Height = 316
    Anchors = [akLeft, akTop, akBottom]
    TabOrder = 7
    inherited Tree: TcxTreeView
      Width = 279
      Height = 316
    end
  end
  object cxGrid1: TcxGrid [13]
    Left = 290
    Top = 89
    Width = 489
    Height = 315
    Enabled = False
    TabOrder = 8
    OnEnter = cxGrid1Enter
    OnExit = cxGrid1Exit
    LookAndFeel.NativeStyle = True
    object cxGrid1DBTableView1: TcxGridDBTableView
      DataController.DataSource = dsDet
      DataController.KeyFieldNames = 'idPresupuestoDet'
      DataController.Summary.DefaultGroupSummaryItems = <>
      DataController.Summary.FooterSummaryItems = <>
      DataController.Summary.SummaryGroups = <>
      NavigatorButtons.ConfirmDelete = False
      OptionsBehavior.FocusFirstCellOnNewRecord = True
      OptionsBehavior.GoToNextCellOnEnter = True
      OptionsBehavior.FocusCellOnCycle = True
      OptionsData.Appending = True
      OptionsView.Navigator = True
      OptionsView.CellAutoHeight = True
      OptionsView.GroupByBox = False
      object cxGrid1DBTableView1idPartida: TcxGridDBColumn
        Caption = 'Partida'
        DataBinding.FieldName = 'idPartida'
        PropertiesClassName = 'TcxLookupComboBoxProperties'
        Properties.ImmediatePost = True
        Properties.KeyFieldNames = 'idPartida'
        Properties.ListColumns = <
          item
            FieldName = 'Partida'
          end>
        Properties.ListOptions.GridLines = glNone
        Properties.ListOptions.ShowHeader = False
        Properties.ListSource = dsPartidas
        Options.Filtering = False
        Width = 165
      end
      object cxGrid1DBTableView1DBColumn1: TcxGridDBColumn
        Caption = 'Unidad'
        DataBinding.FieldName = 'idUnidad'
        PropertiesClassName = 'TcxLookupComboBoxProperties'
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
      end
      object cxGrid1DBTableView1Cantidad: TcxGridDBColumn
        DataBinding.FieldName = 'Cantidad'
        Options.Filtering = False
        Width = 52
      end
      object cxGrid1DBTableView1CostoUnidad: TcxGridDBColumn
        Caption = 'Costo Und.'
        DataBinding.FieldName = 'CostoUnidad'
        Options.Filtering = False
      end
      object cxGrid1DBTableView1Notas: TcxGridDBColumn
        DataBinding.FieldName = 'Notas'
        Options.Filtering = False
        Width = 155
      end
    end
    object cxGrid1Level1: TcxGridLevel
      GridView = cxGrid1DBTableView1
    end
  end
  object edPresupuesto: TcxDBTextEdit [14]
    Left = 72
    Top = 38
    Width = 477
    Height = 21
    DataBinding.DataField = 'Presupuesto'
    DataBinding.DataSource = DS
    Style.LookAndFeel.NativeStyle = True
    TabOrder = 9
  end
  object cxDBLookupComboBox1: TcxDBLookupComboBox [15]
    Left = 72
    Top = 62
    Width = 389
    Height = 21
    DataBinding.DataField = 'idProyecto'
    DataBinding.DataSource = DS
    Properties.ImmediatePost = True
    Properties.KeyFieldNames = 'idProyecto'
    Properties.ListColumns = <
      item
        FieldName = 'ProyectoDesc'
      end>
    Properties.ListSource = dsControles
    Style.LookAndFeel.NativeStyle = True
    TabOrder = 10
  end
  object cxDBLookupComboBox2: TcxDBLookupComboBox [16]
    Left = 524
    Top = 62
    Width = 205
    Height = 21
    DataBinding.DataField = 'idPresupuestoTipo'
    DataBinding.DataSource = DS
    Properties.KeyFieldNames = 'idPresupuestoTipo'
    Properties.ListColumns = <
      item
        FieldName = 'PresupuestoTipo'
      end>
    Properties.ListSource = dsTipos
    Style.LookAndFeel.NativeStyle = True
    TabOrder = 11
  end
  object cxButton1: TcxButton [17]
    Left = 238
    Top = 409
    Width = 51
    Height = 43
    Action = AEditar
    Anchors = [akLeft, akBottom]
    TabOrder = 12
    Glyph.Data = {
      36040000424D3604000000000000360000002800000010000000100000000100
      2000000000000004000000000000000000000000000000000000FF00FF000073
      AD000073AD000073AD000073AD000073AD000073AD000073AD000073AD000073
      AD00006B08000073AD000073AD000073AD00FF00FF00FF00FF000073AD00108C
      C60052B5E7006BCEFF004ABDF7004ABDF7004ABDF7004ABDF7004ABDF7004ABD
      F700006B0800006B0800219CCE000073AD00FF00FF00FF00FF000073AD0031AD
      E7002194C6008CDEFF0052C6FF0052C6F70052C6FF0052C6F70052C6FF0052C6
      FF00006B080010A52900006B08006BCEE7000073AD00FF00FF000073AD0052CE
      FF000073AD009CE7FF005AD6FF00006B0800006B0800006B0800006B0800006B
      0800006B080018AD310010A52900006B08000073AD00FF00FF000073AD005AD6
      FF0008739C0094ADB50094949400006B080042E77B0042DE730039D66B0031CE
      5A0029BD4A0021B5390018AD310010A52900006B0800FF00FF000073AD006BDE
      FF00396B840063B5C600E7EFD600006B080042E77B0042E77B0042DE730039D6
      6B0031CE5A0029C64A0021B5390018AD310010A52900006B08000073AD0073E7
      FF007B636B001084B500FFFFFF00006B080042E77B0042E77B0042E77B0042DE
      730039D66B0031CE5A0029C64A0021B53900006B08000073AD000073AD007BEF
      FF009C6B6300107BAD000073AD00006B0800006B0800006B0800006B0800006B
      0800006B080039D6630031CE5A00006B08000073AD000073AD000073AD0084F7
      FF00A5736300F7E7D600FFF7DE00FFE7CE00FFE7C600FFDEBD00FFDEB500FFD6
      A500006B080042DE7300006B0800FF00FF00FF00FF00FF00FF000073AD00FFFF
      FF00B57B6300F7EFE700FFFFEF00FFEFDE00FFEFD600FFE7CE00FFE7C600FFDE
      BD00006B0800006B0800006BA500FF00FF00FF00FF00FF00FF00FF00FF000073
      AD00BD8C6B00FFF7EF00FFFFFF00FFF7EF00FFF7E700FFF7E700FFF7E700F7E7
      CE00006B08000073AD00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00
      FF00CE947300FFF7EF00FFFFFF00FFFFFF00FFFFF700E7CEC600D6B5AD00BDA5
      9C0073424200FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00
      FF00D69C7300FFF7F700FFFFFF00FFFFFF00FFFFFF00A5635A00A5635A00A563
      5A00A5635A00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00
      FF00DEA57B00FFF7EF00FFFFFF00FFFFFF00FFFFFF00A5635A00E7A55A00EF9C
      3900FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00
      FF00E7AD7B00D6946B00D6946B00D6946B00D6946B00A5635A00D69C6300FF00
      FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00
      FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00
      FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00FF00}
    Layout = blGlyphTop
    LookAndFeel.NativeStyle = True
  end
  inherited DS: TwwDataSource [18]
    DataSet = RS
  end
  inherited Acciones: TActionList [19]
  end
  object rsPartidas: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    CommandText = 'proyRSPartidas;1'
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
        Name = '@orden'
        Attributes = [paNullable]
        DataType = ftString
        Size = 10
        Value = Null
      end>
    Left = 174
    Top = 268
    object rsPartidasidPartida: TStringField
      FieldName = 'idPartida'
      Size = 16
    end
    object rsPartidasPartida: TStringField
      FieldName = 'Partida'
      Size = 100
    end
    object rsPartidasidUnidad: TStringField
      FieldName = 'idUnidad'
      Size = 16
    end
  end
  object RS: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    LockType = ltBatchOptimistic
    OnNewRecord = RSNewRecord
    CommandText = 'proyRSPresupuesto'
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
        Name = '@idPrespuesto'
        Attributes = [paNullable]
        DataType = ftGuid
        Value = Null
      end>
    Left = 156
    Top = 140
    object RSidPresupuesto: TGuidField
      FieldName = 'idPresupuesto'
      FixedChar = True
      Size = 38
    end
    object RSidProyecto: TGuidField
      FieldName = 'idProyecto'
      OnValidate = RSidProyectoValidate
      FixedChar = True
      Size = 38
    end
    object RSPresupuesto: TStringField
      FieldName = 'Presupuesto'
      Size = 200
    end
    object RSidPresupuestoTipo: TStringField
      FieldName = 'idPresupuestoTipo'
      Size = 16
    end
  end
  object rsListaProyectos: TADODataSet
    Connection = dm.Coneccion
    LockType = ltReadOnly
    CommandText = 'proyProyectosControl;1'
    CommandType = cmdStoredProc
    Parameters = <
      item
        Name = '@RETURN_VALUE'
        DataType = ftInteger
        Direction = pdReturnValue
        Precision = 10
        Value = 0
      end>
    Left = 354
    Top = 138
    object rsListaProyectosidProyecto: TGuidField
      FieldName = 'idProyecto'
      ReadOnly = True
      FixedChar = True
      Size = 38
    end
    object rsListaProyectosProyecto: TStringField
      FieldName = 'Proyecto'
      ReadOnly = True
      Size = 17
    end
    object rsListaProyectosProyectoDesc: TStringField
      FieldName = 'ProyectoDesc'
      ReadOnly = True
      Size = 100
    end
  end
  object rsTipo: TADODataSet
    Connection = dm.Coneccion
    LockType = ltReadOnly
    CommandText = 'proyRSPresupuestoTipo;1'
    CommandType = cmdStoredProc
    Parameters = <>
    Left = 516
    Top = 172
    object rsTipoidPresupuestoTipo: TStringField
      FieldName = 'idPresupuestoTipo'
      Size = 16
    end
    object rsTipoPresupuestoTipo: TStringField
      FieldName = 'PresupuestoTipo'
      Size = 100
    end
  end
  object dsControles: TwwDataSource
    AutoEdit = False
    DataSet = rsListaProyectos
    OnUpdateData = DSUpdateData
    Left = 415
    Top = 291
  end
  object dsTipos: TwwDataSource
    AutoEdit = False
    DataSet = rsTipo
    OnUpdateData = DSUpdateData
    Left = 433
    Top = 135
  end
  object rsDet: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    LockType = ltBatchOptimistic
    OnNewRecord = rsDetNewRecord
    CommandText = 'proyRSPresupuestoDet;1'
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
        Name = '@idPrespuesto'
        Attributes = [paNullable]
        DataType = ftGuid
        Value = Null
      end>
    Left = 206
    Top = 112
    object rsDetidPresupuestoDet: TGuidField
      FieldName = 'idPresupuestoDet'
      FixedChar = True
      Size = 38
    end
    object rsDetidPresupuesto: TGuidField
      FieldName = 'idPresupuesto'
      FixedChar = True
      Size = 38
    end
    object rsDetidProyecto: TGuidField
      FieldName = 'idProyecto'
      FixedChar = True
      Size = 38
    end
    object rsDetidPartida: TStringField
      FieldName = 'idPartida'
      OnValidate = rsDetidPartidaValidate
      Size = 16
    end
    object rsDetCantidad: TFloatField
      FieldName = 'Cantidad'
    end
    object rsDetCostoUnidad: TFloatField
      FieldName = 'CostoUnidad'
    end
    object rsDetNotas: TStringField
      FieldName = 'Notas'
      Size = 200
    end
    object rsDetidUnidad: TStringField
      FieldName = 'idUnidad'
      Size = 16
    end
  end
  object dsDet: TwwDataSource
    AutoEdit = False
    DataSet = rsDet
    OnUpdateData = DSUpdateData
    Left = 313
    Top = 285
  end
  object dsPartidas: TDataSource
    DataSet = rsPartidas
    Left = 50
    Top = 206
  end
  object rsUnidad: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    LockType = ltReadOnly
    CommandText = 'svRSUnidad;1'
    CommandType = cmdStoredProc
    Parameters = <>
    Left = 52
    Top = 338
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
    Left = 166
    Top = 328
  end
  object rsRPT: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    LockType = ltReadOnly
    CommandText = 'proyPresupuestoRPT;1'
    CommandType = cmdStoredProc
    Parameters = <
      item
        Name = '@RETURN_VALUE'
        DataType = ftInteger
        Direction = pdReturnValue
        Precision = 10
        Value = Null
      end
      item
        Name = '@idPresupuesto'
        Attributes = [paNullable]
        DataType = ftGuid
        Value = Null
      end>
    Left = 628
    Top = 194
    object rsRPTidPresupuesto: TGuidField
      FieldName = 'idPresupuesto'
      FixedChar = True
      Size = 38
    end
    object rsRPTidProyecto: TGuidField
      FieldName = 'idProyecto'
      FixedChar = True
      Size = 38
    end
    object rsRPTPresupuesto: TStringField
      FieldName = 'Presupuesto'
      Size = 200
    end
    object rsRPTidPresupuestoTipo: TStringField
      FieldName = 'idPresupuestoTipo'
      Size = 16
    end
    object rsRPTProyecto: TStringField
      FieldName = 'Proyecto'
      Size = 16
    end
    object rsRPTProyectoDesc: TStringField
      FieldName = 'ProyectoDesc'
      Size = 100
    end
    object rsRPTidPartida: TStringField
      FieldName = 'idPartida'
      Size = 16
    end
    object rsRPTPartida: TStringField
      FieldName = 'Partida'
      Size = 100
    end
    object rsRPTidUnidad: TStringField
      FieldName = 'idUnidad'
      Size = 16
    end
    object rsRPTCantidad: TFloatField
      FieldName = 'Cantidad'
    end
    object rsRPTCostoUnidad: TFloatField
      FieldName = 'CostoUnidad'
    end
    object rsRPTDetProyecto: TStringField
      FieldName = 'DetProyecto'
      Size = 16
    end
    object rsRPTDetProyectoDesc: TStringField
      FieldName = 'DetProyectoDesc'
      Size = 100
    end
    object rsRPTNotas: TStringField
      FieldName = 'Notas'
      Size = 200
    end
    object rsRPTTotal: TFloatField
      FieldName = 'Total'
      ReadOnly = True
    end
  end
  object dsRPT: TDataSource
    DataSet = rsRPT
    Left = 688
    Top = 202
  end
  object plRPT: TppDBPipeline
    DataSource = dsRPT
    UserName = 'Prespuesto'
    Left = 632
    Top = 260
    object plRPTppField1: TppField
      FieldAlias = 'idPresupuesto'
      FieldName = 'idPresupuesto'
      FieldLength = 0
      DisplayWidth = 0
      Position = 0
    end
    object plRPTppField2: TppField
      FieldAlias = 'idProyecto'
      FieldName = 'idProyecto'
      FieldLength = 38
      DisplayWidth = 38
      Position = 1
    end
    object plRPTppField3: TppField
      FieldAlias = 'Presupuesto'
      FieldName = 'Presupuesto'
      FieldLength = 200
      DisplayWidth = 200
      Position = 2
    end
    object plRPTppField4: TppField
      FieldAlias = 'idPresupuestoTipo'
      FieldName = 'idPresupuestoTipo'
      FieldLength = 16
      DisplayWidth = 16
      Position = 3
    end
    object plRPTppField5: TppField
      FieldAlias = 'Proyecto'
      FieldName = 'Proyecto'
      FieldLength = 16
      DisplayWidth = 16
      Position = 4
    end
    object plRPTppField6: TppField
      FieldAlias = 'ProyectoDesc'
      FieldName = 'ProyectoDesc'
      FieldLength = 100
      DisplayWidth = 100
      Position = 5
    end
    object plRPTppField7: TppField
      FieldAlias = 'idPartida'
      FieldName = 'idPartida'
      FieldLength = 16
      DisplayWidth = 16
      Position = 6
    end
    object plRPTppField8: TppField
      FieldAlias = 'Partida'
      FieldName = 'Partida'
      FieldLength = 100
      DisplayWidth = 100
      Position = 7
    end
    object plRPTppField9: TppField
      FieldAlias = 'idUnidad'
      FieldName = 'idUnidad'
      FieldLength = 16
      DisplayWidth = 16
      Position = 8
    end
    object plRPTppField10: TppField
      Alignment = taRightJustify
      FieldAlias = 'Cantidad'
      FieldName = 'Cantidad'
      FieldLength = 0
      DataType = dtDouble
      DisplayWidth = 10
      Position = 9
    end
    object plRPTppField11: TppField
      Alignment = taRightJustify
      FieldAlias = 'CostoUnidad'
      FieldName = 'CostoUnidad'
      FieldLength = 0
      DataType = dtDouble
      DisplayWidth = 10
      Position = 10
    end
    object plRPTppField12: TppField
      FieldAlias = 'DetProyecto'
      FieldName = 'DetProyecto'
      FieldLength = 16
      DisplayWidth = 16
      Position = 11
    end
    object plRPTppField13: TppField
      FieldAlias = 'DetProyectoDesc'
      FieldName = 'DetProyectoDesc'
      FieldLength = 100
      DisplayWidth = 100
      Position = 12
    end
    object plRPTppField14: TppField
      FieldAlias = 'Notas'
      FieldName = 'Notas'
      FieldLength = 200
      DisplayWidth = 200
      Position = 13
    end
    object plRPTppField15: TppField
      Alignment = taRightJustify
      FieldAlias = 'Total'
      FieldName = 'Total'
      FieldLength = 0
      DataType = dtDouble
      DisplayWidth = 10
      Position = 14
    end
  end
  object Report: TppReport
    AutoStop = False
    DataPipeline = plRPT
    PassSetting = psTwoPass
    PrinterSetup.BinName = 'Default'
    PrinterSetup.DocumentName = 'Report'
    PrinterSetup.Orientation = poLandscape
    PrinterSetup.PaperName = 'Letter'
    PrinterSetup.PrinterName = 'Default'
    PrinterSetup.mmMarginBottom = 6350
    PrinterSetup.mmMarginLeft = 6350
    PrinterSetup.mmMarginRight = 6350
    PrinterSetup.mmMarginTop = 6350
    PrinterSetup.mmPaperHeight = 215900
    PrinterSetup.mmPaperWidth = 279401
    PrinterSetup.PaperSize = 1
    DeviceType = 'Screen'
    OutlineSettings.CreateNode = False
    OutlineSettings.CreatePageNodes = True
    OutlineSettings.Enabled = False
    OutlineSettings.Visible = False
    TextSearchSettings.DefaultString = '<EncontrarTexto>'
    TextSearchSettings.Enabled = True
    Left = 692
    Top = 264
    Version = '7.04'
    mmColumnWidth = 0
    DataPipelineName = 'plRPT'
    object ppTitleBand1: TppTitleBand
      mmBottomOffset = 0
      mmHeight = 1323
      mmPrintPosition = 0
    end
    object ppHeaderBand1: TppHeaderBand
      mmBottomOffset = 0
      mmHeight = 20373
      mmPrintPosition = 0
      object ppLabel1: TppLabel
        UserName = 'Label1'
        AutoSize = False
        Caption = 'Prespuesto'
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clNavy
        Font.Name = 'Tahoma'
        Font.Size = 20
        Font.Style = [fsBold]
        Transparent = True
        mmHeight = 8467
        mmLeft = 794
        mmTop = 1588
        mmWidth = 63500
        BandType = 0
      end
      object ppDBText7: TppDBText
        UserName = 'DBText7'
        DataField = 'Presupuesto'
        DataPipeline = plRPT
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clNavy
        Font.Name = 'TIMES NEW ROMAN'
        Font.Size = 9
        Font.Style = []
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3704
        mmLeft = 16669
        mmTop = 10583
        mmWidth = 153723
        BandType = 0
      end
      object ppDBText8: TppDBText
        UserName = 'DBText8'
        DataField = 'ProyectoDesc'
        DataPipeline = plRPT
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clNavy
        Font.Name = 'TIMES NEW ROMAN'
        Font.Size = 9
        Font.Style = []
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3704
        mmLeft = 44979
        mmTop = 15610
        mmWidth = 125677
        BandType = 0
      end
      object ppDBText9: TppDBText
        UserName = 'DBText9'
        DataField = 'Proyecto'
        DataPipeline = plRPT
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clNavy
        Font.Name = 'TIMES NEW ROMAN'
        Font.Size = 9
        Font.Style = []
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3704
        mmLeft = 16404
        mmTop = 15610
        mmWidth = 26458
        BandType = 0
      end
      object ppSystemVariable1: TppSystemVariable
        UserName = 'SystemVariable1'
        VarType = vtPrintDateTime
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clNavy
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        TextAlignment = taRightJustified
        Transparent = True
        mmHeight = 3440
        mmLeft = 212461
        mmTop = 2117
        mmWidth = 51594
        BandType = 0
      end
      object ppSystemVariable2: TppSystemVariable
        UserName = 'SystemVariable2'
        VarType = vtPageSetDesc
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clNavy
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        TextAlignment = taRightJustified
        Transparent = True
        mmHeight = 3440
        mmLeft = 229394
        mmTop = 6085
        mmWidth = 34396
        BandType = 0
      end
      object ppLine1: TppLine
        UserName = 'Line1'
        ParentWidth = True
        Weight = 0.750000000000000000
        mmHeight = 1058
        mmLeft = 0
        mmTop = 20108
        mmWidth = 266701
        BandType = 0
      end
    end
    object ppDetailBand1: TppDetailBand
      mmBottomOffset = 0
      mmHeight = 4498
      mmPrintPosition = 0
      object ppShape2: TppShape
        UserName = 'Shape2'
        ParentHeight = True
        ParentWidth = True
        mmHeight = 4498
        mmLeft = 0
        mmTop = 0
        mmWidth = 266701
        BandType = 4
      end
      object ppDBText2: TppDBText
        UserName = 'DBText2'
        DataField = 'idPartida'
        DataPipeline = plRPT
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clBlack
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3260
        mmLeft = 1323
        mmTop = 529
        mmWidth = 26458
        BandType = 4
      end
      object ppDBText3: TppDBText
        UserName = 'DBText3'
        DataField = 'Partida'
        DataPipeline = plRPT
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clBlack
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3175
        mmLeft = 29369
        mmTop = 529
        mmWidth = 105834
        BandType = 4
      end
      object ppDBText4: TppDBText
        UserName = 'DBText4'
        DataField = 'Cantidad'
        DataPipeline = plRPT
        DisplayFormat = '#,0.00;(#,0.00)'
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clBlack
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        TextAlignment = taRightJustified
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3175
        mmLeft = 139965
        mmTop = 529
        mmWidth = 18256
        BandType = 4
      end
      object ppDBText5: TppDBText
        UserName = 'DBText5'
        DataField = 'idUnidad'
        DataPipeline = plRPT
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clBlack
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3175
        mmLeft = 159544
        mmTop = 529
        mmWidth = 26458
        BandType = 4
      end
      object ppDBText6: TppDBText
        UserName = 'DBText6'
        DataField = 'CostoUnidad'
        DataPipeline = plRPT
        DisplayFormat = '#,0.00;(#,0.00)'
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clBlack
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        TextAlignment = taRightJustified
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3175
        mmLeft = 187325
        mmTop = 529
        mmWidth = 25135
        BandType = 4
      end
      object ppDBText11: TppDBText
        UserName = 'DBText11'
        DataField = 'Total'
        DataPipeline = plRPT
        DisplayFormat = '#,0.00;(#,0.00)'
        Font.Charset = DEFAULT_CHARSET
        Font.Color = clBlack
        Font.Name = 'Verdana'
        Font.Size = 8
        Font.Style = []
        TextAlignment = taRightJustified
        Transparent = True
        DataPipelineName = 'plRPT'
        mmHeight = 3175
        mmLeft = 214048
        mmTop = 529
        mmWidth = 31221
        BandType = 4
      end
      object ppLine3: TppLine
        UserName = 'Line3'
        ParentHeight = True
        Position = lpLeft
        Weight = 0.750000000000000000
        mmHeight = 4498
        mmLeft = 28575
        mmTop = 0
        mmWidth = 13229
        BandType = 4
      end
      object ppLine4: TppLine
        UserName = 'Line4'
        ParentHeight = True
        Position = lpLeft
        Weight = 0.750000000000000000
        mmHeight = 4498
        mmLeft = 138377
        mmTop = 0
        mmWidth = 6350
        BandType = 4
      end
      object ppLine6: TppLine
        UserName = 'Line6'
        ParentHeight = True
        Position = lpLeft
        Weight = 0.750000000000000000
        mmHeight = 4498
        mmLeft = 158750
        mmTop = 0
        mmWidth = 6350
        BandType = 4
      end
      object ppLine7: TppLine
        UserName = 'Line7'
        ParentHeight = True
        Position = lpLeft
        Weight = 0.750000000000000000
        mmHeight = 4498
        mmLeft = 186532
        mmTop = 0
        mmWidth = 6350
        BandType = 4
      end
      object ppLine8: TppLine
        UserName = 'Line8'
        ParentHeight = True
        Position = lpLeft
        Weight = 0.750000000000000000
        mmHeight = 4498
        mmLeft = 212990
        mmTop = 0
        mmWidth = 6350
        BandType = 4
      end
    end
    object ppFooterBand1: TppFooterBand
      mmBottomOffset = 0
      mmHeight = 2381
      mmPrintPosition = 0
      object ppLine5: TppLine
        UserName = 'Line5'
        Pen.Color = clGray
        Pen.Width = 2
        ParentWidth = True
        Weight = 1.500000000000000000
        mmHeight = 1058
        mmLeft = 0
        mmTop = 1323
        mmWidth = 266701
        BandType = 8
      end
    end
    object ppGroup1: TppGroup
      BreakName = 'DetProyecto'
      DataPipeline = plRPT
      OutlineSettings.CreateNode = True
      UserName = 'Group1'
      mmNewColumnThreshold = 0
      mmNewPageThreshold = 0
      DataPipelineName = 'plRPT'
      object ppGroupHeaderBand1: TppGroupHeaderBand
        mmBottomOffset = 0
        mmHeight = 10319
        mmPrintPosition = 0
        object ppShape1: TppShape
          UserName = 'Shape1'
          ParentWidth = True
          mmHeight = 4498
          mmLeft = 0
          mmTop = 5821
          mmWidth = 266701
          BandType = 3
          GroupNo = 0
        end
        object ppDBText1: TppDBText
          UserName = 'DBText1'
          DataField = 'DetProyecto'
          DataPipeline = plRPT
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'TIMES NEW ROMAN'
          Font.Size = 9
          Font.Style = []
          Transparent = True
          DataPipelineName = 'plRPT'
          mmHeight = 3725
          mmLeft = 1323
          mmTop = 529
          mmWidth = 26458
          BandType = 3
          GroupNo = 0
        end
        object ppLabel2: TppLabel
          UserName = 'Label2'
          AutoSize = False
          Caption = 'Partida'
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'Verdana'
          Font.Size = 8
          Font.Style = [fsBold]
          Transparent = True
          mmHeight = 3387
          mmLeft = 1323
          mmTop = 6350
          mmWidth = 13758
          BandType = 3
          GroupNo = 0
        end
        object ppLabel3: TppLabel
          UserName = 'Label3'
          AutoSize = False
          Caption = 'Descripcion'
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'Verdana'
          Font.Size = 8
          Font.Style = [fsBold]
          Transparent = True
          mmHeight = 3440
          mmLeft = 29369
          mmTop = 6350
          mmWidth = 27517
          BandType = 3
          GroupNo = 0
        end
        object ppLabel4: TppLabel
          UserName = 'Label4'
          AutoSize = False
          Caption = 'Cantidad'
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'Verdana'
          Font.Size = 8
          Font.Style = [fsBold]
          TextAlignment = taRightJustified
          Transparent = True
          mmHeight = 3440
          mmLeft = 141023
          mmTop = 6350
          mmWidth = 17198
          BandType = 3
          GroupNo = 0
        end
        object ppLabel5: TppLabel
          UserName = 'Label5'
          AutoSize = False
          Caption = 'Unidad'
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'Verdana'
          Font.Size = 8
          Font.Style = [fsBold]
          Transparent = True
          mmHeight = 3387
          mmLeft = 159544
          mmTop = 6350
          mmWidth = 13494
          BandType = 3
          GroupNo = 0
        end
        object ppLabel6: TppLabel
          UserName = 'Label6'
          AutoSize = False
          Caption = 'Costo/Unidad'
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'Verdana'
          Font.Size = 8
          Font.Style = [fsBold]
          TextAlignment = taRightJustified
          Transparent = True
          mmHeight = 3387
          mmLeft = 187325
          mmTop = 6350
          mmWidth = 25135
          BandType = 3
          GroupNo = 0
        end
        object ppDBText10: TppDBText
          UserName = 'DBText10'
          DataField = 'DetProyectoDesc'
          DataPipeline = plRPT
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'TIMES NEW ROMAN'
          Font.Size = 9
          Font.Style = []
          Transparent = True
          DataPipelineName = 'plRPT'
          mmHeight = 3704
          mmLeft = 29369
          mmTop = 529
          mmWidth = 125677
          BandType = 3
          GroupNo = 0
        end
        object ppLabel7: TppLabel
          UserName = 'Label7'
          AutoSize = False
          Caption = 'Total'
          Font.Charset = DEFAULT_CHARSET
          Font.Color = clNavy
          Font.Name = 'Verdana'
          Font.Size = 8
          Font.Style = [fsBold]
          TextAlignment = taRightJustified
          Transparent = True
          mmHeight = 3387
          mmLeft = 214048
          mmTop = 6350
          mmWidth = 31221
          BandType = 3
          GroupNo = 0
        end
        object ppLine9: TppLine
          UserName = 'Line9'
          Position = lpLeft
          Weight = 0.750000000000000000
          mmHeight = 4498
          mmLeft = 28575
          mmTop = 5821
          mmWidth = 13229
          BandType = 3
          GroupNo = 0
        end
        object ppLine10: TppLine
          UserName = 'Line10'
          Position = lpLeft
          Weight = 0.750000000000000000
          mmHeight = 4498
          mmLeft = 138377
          mmTop = 5821
          mmWidth = 13229
          BandType = 3
          GroupNo = 0
        end
        object ppLine11: TppLine
          UserName = 'Line101'
          Position = lpLeft
          Weight = 0.750000000000000000
          mmHeight = 4498
          mmLeft = 158750
          mmTop = 5821
          mmWidth = 13229
          BandType = 3
          GroupNo = 0
        end
        object ppLine12: TppLine
          UserName = 'Line12'
          Position = lpLeft
          Weight = 0.750000000000000000
          mmHeight = 4498
          mmLeft = 186532
          mmTop = 5821
          mmWidth = 13229
          BandType = 3
          GroupNo = 0
        end
        object ppLine13: TppLine
          UserName = 'Line13'
          Position = lpLeft
          Weight = 0.750000000000000000
          mmHeight = 4498
          mmLeft = 212990
          mmTop = 5821
          mmWidth = 13229
          BandType = 3
          GroupNo = 0
        end
      end
      object ppGroupFooterBand1: TppGroupFooterBand
        mmBottomOffset = 0
        mmHeight = 0
        mmPrintPosition = 0
      end
    end
  end
  object ProyectoPartida: TADODataSet
    Connection = dm.Coneccion
    CursorType = ctStatic
    CommandText = 'ProyrsProyectoPartida;1'
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
    Left = 48
    Top = 108
    object ProyectoPartidaidProyectoPartida: TGuidField
      FieldName = 'idProyectoPartida'
      FixedChar = True
      Size = 38
    end
    object ProyectoPartidaidProyecto: TGuidField
      FieldName = 'idProyecto'
      FixedChar = True
      Size = 38
    end
    object ProyectoPartidaidPartida: TStringField
      FieldName = 'idPartida'
      Size = 16
    end
    object ProyectoPartidaValor: TBCDField
      FieldName = 'Valor'
      DisplayFormat = '#,0.00;(#,0.00)'
      Precision = 18
      Size = 2
    end
    object ProyectoPartidaProyectoPartida: TStringField
      FieldName = 'ProyectoPartida'
      Size = 200
    end
    object ProyectoPartidaCantidad: TFloatField
      FieldName = 'Cantidad'
    end
    object ProyectoPartidaidUnidad: TStringField
      FieldName = 'idUnidad'
      Size = 16
    end
  end
end
