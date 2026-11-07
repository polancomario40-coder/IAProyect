"""Siembra el catalogo de estimaciones y las listas de precios reales.

Los valores se exportaron de estimaciones/db/estimaciones.db el 2026-08-24.
Se mantienen hardcodeados deliberadamente para que un checkout limpio pueda
reconstruir un sistema funcional sin depender de los Excel fuente.
"""
import argparse
import os
import sqlite3


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")

CATALOGO_ESTIMACION = [
    ('DOMICEM', 'CAVERNAS', 1, '1', 'Hormigón 100 kg/cm2, Ag 3/4", T35C, REV. 6" +/-1"', 109.0),
     ('DOMICEM', 'CAVERNAS', 2, '2', 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"', 111.0),
     ('DOMICEM', 'CAVERNAS', 3, '3', 'Hormigón 210 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"', 122.0),
     ('DOMICEM', 'CAVERNAS', 4, '4', 'Hormigón 210 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.', 130.0),
     ('DOMICEM', 'CAVERNAS', 5, '5', 'Hormigón 240 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.', 136.3),
     ('DOMICEM', 'CAVERNAS', 6, '6', 'Hormigón 240 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"', 126.3),
     ('DOMICEM', 'CAVERNAS', 7, '7', 'Hormigón 280 kg/cm2, Ag 3/8",T 32C, rev. 7" +/- 1", imp', 156.45),
     ('DOMICEM', 'CAVERNAS', 8, '8', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.', 145.0),
     ('DOMICEM', 'CAVERNAS', 9, '9', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", acelerado', 170.0),
     ('DOMICEM', 'CAVERNAS', 10, '10', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1".', 133.0),
     ('DOMICEM',
      'CAVERNAS',
      11,
      '11',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp',
      186.98),
     ('DOMICEM',
      'CAVERNAS',
      12,
      '12',
      'FC 350kg/cm2, AMB IIIA, Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp, ac 7 Dias',
      194.07),
     ('DOMICEM', 'CAVERNAS', 13, '13', 'Mortero Fc80 kg/cm2, 100% arena, Temp. 35C, rev. 6"+/- 1".', 134.69),
     ('DOMICEM', 'VIVIENDAS', 1, '1', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 109.0),
     ('DOMICEM', 'VIVIENDAS', 2, '2', 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 7" +/- 1"', 111.0),
     ('DOMICEM', 'VIVIENDAS', 3, '3', 'Hormigón 210 kg/cm2, Ag 3/8",T 35C, rev. 6" +/- 1"', 125.56),
     ('DOMICEM', 'VIVIENDAS', 4, '4', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"', 133.0),
     ('DOMICEM', 'VIVIENDAS', 5, '5', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", acelerado', 170.0),
     ('DOMICEM', 'VIVIENDAS', 6, '6', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.', 145.0),
     ('DOMICEM', 'VIVIENDAS', 7, '7', 'Hormigón 280 kg/cm2, Ag 3/8",T 35C, rev. 6" +/- 1",', 143.04),
     ('DOMICEM', 'VIVIENDAS', 8, '8', 'Mortero Fc80 kg/cm2, 100% arena, Temp. 35C, rev. 6"+/- 1".', 134.69),
     ('DOMICEM', 'VIVIENDAS', 9, '9', 'Hormigón 280 kg/cm2, Ag 3/8",T 35C, rev. 8" +/- 1",', 147.99),
     ('DOMICEM', 'MACAO 2', 1, '1', 'Hormigón Fc100 kg/cm2,  Agg 3/4", Temp. 35C, rev. 6"+/- 1".  PLANTILLA', 108.5),
     ('DOMICEM',
      'MACAO 2',
      2,
      '2',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 6"+/- 1", antideslave. '
      'PILOTES',
      218.2),
     ('DOMICEM',
      'MACAO 2',
      3,
      '3',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1" (CIMENTACION TORRES '
      '/ TORRE GRUA)',
      191.27),
     ('DOMICEM',
      'MACAO 2',
      4,
      '5',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1", imp. MURO DE '
      'CONTENCION',
      200.01),
     ('DOMICEM',
      'MACAO 2',
      5,
      '6',
      'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1".  COLUMNAS - MUROS',
      154.02),
     ('DOMICEM',
      'MACAO 2',
      6,
      '7',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Hidrofugo. LOSAS Y '
      'VIGAS (HIDROFUGO)',
      186.98),
     ('DOMICEM',
      'MACAO 2',
      7,
      '8',
      'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.45, rev. 6"+/- 1".  LOSAS Y VIGAS',
      159.1),
     ('DOMICEM',
      'MACAO 2',
      8,
      '9',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/8", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1", imp',
      208.01),
     ('DOMICEM', 'PATIO DE MANIOBRAS-TRB', 1, '1', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 108.5),
     ('DOMICEM',
      'PATIO DE MANIOBRAS-TRB',
      2,
      '2',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1"',
      191.27),
     ('DOMICEM',
      'PATIO DE MANIOBRAS-TRB',
      3,
      '3',
      'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1".',
      154.02),
     ('DOMICEM',
      'PATIO DE MANIOBRAS-TRB',
      4,
      '4',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp',
      186.98),
     ('VMO', 'CANCHAS', 1, '1', 'Hormigón 210,agg 3/4, Temp 35C, rev. 6+/-1', 122.0),
     ('VMO', 'CANCHAS', 2, '2', 'Mortero Fc80 kg/cm2, 100% arena, Temp. 35C, rev. 6"+/- 1", imp.', 147.19),
     ('VMO', 'CANCHAS', 3, '3', 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp', 140.0),
     ('VMO', 'CEDIS', 1, '1', 'PAVIMENTACION RIGIDA MR32, T35C, Directo', 152.86),
     ('VMO', 'CEDIS', 2, '2', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 109.0),
     ('VMO', 'CEDIS', 3, '3', 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"', 111.0),
     ('VMO', 'CEDIS', 4, '4', 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1" Imp.', 119.0),
     ('VMO', 'CEDIS', 5, '5', 'Hormigón 150 kg/cm2, Ag 3/8",T 35C, rev. 6" +/- 1"', 117.0),
     ('VMO', 'CEDIS', 6, '6', 'Hormigón 180 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"', 121.6),
     ('VMO', 'CEDIS', 7, '7', 'Hormigón 180 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1" imp', 129.6),
     ('VMO', 'CEDIS', 8, '8', 'Hormigón 180 kg/cm2, Ag 3/8",T 35C, rev. 6" +/- 1"', 127.6),
     ('VMO', 'CEDIS', 9, '9', 'Hormigón 210 kg/cm2, Ag 3/4",T 32C, rev. 6" +/- 1"', 122.0),
     ('VMO', 'CEDIS', 10, '10', 'Hormigón 210 kg/cm2, Ag 3/4",T 32C, rev. 6" +/- 1", imp', 133.0),
     ('VMO', 'CEDIS', 11, '11', 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1"', 133.0),
     ('VMO', 'CEDIS', 12, '12', 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp', 140.0),
     # 2026-10-20: no esta en el documento del cliente. Aparecieron 17 conduces
     # (128 m3, 2026-09-22 a 2026-10-01) sin renglon; precio y clave confirmados
     # por el usuario. La descripcion es la de los conduces.
     ('VMO', 'CEDIS', 13, '13', 'PAVIMENTACION RIGIDA MR-42, T35C', 166.45),
     ('VMO', 'PATIO DE MANIOBRAS-TRA', 1, '1', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 109.0),
     ('VMO',
      'PATIO DE MANIOBRAS-TRA',
      2,
      '3',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 6"+/- 1".',
      190.12),
     ('VMO',
      'PATIO DE MANIOBRAS-TRA',
      3,
      '2',
      'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1".',
      154.02),
     ('VMO',
      'PATIO DE MANIOBRAS-TRA',
      4,
      '4',
      'Hormigon 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg,\nrev. 6" +/- 1", Hidrofugo.',
      186.98),
     ('VMO', 'PODIUM-1-2-3', 1, '1', 'Mortero fc250, 100% arena, Temp 32C, rev. 6+/-1', 148.11),
     ('VMO', 'PODIUM-1-2-3', 2, '2', 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1"acelerado', 175.0),
     ('VMO', 'PODIUM-1-2-3', 3, '3', 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1"Fibra.', 142.0),
     ('VMO', 'EXTERIORES', 1, '1', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 109.0),
     ('VMO', 'EXTERIORES', 2, '2', 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 6"+/- 1".', 111.0),
     ('VMO', 'EXTERIORES', 3, '3', 'Hormigón 210,agg 3/4, Temp 35C, rev. 6+/-1', 124.0),
     ('VMO', 'EXTERIORES', 4, '4', 'Hormigón 210 kg/cm2, Ag 3/4",T 32C, rev. imp', 133.0),
     ('VMO', 'EXTERIORES', 5, '5', 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1"', 133.0),
     ('VMO', 'EXTERIORES', 6, '6', 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp', 140.0),
     ('VMO', 'EXTERIORES', 7, '7', 'Hormigon 250kg/cm2, AMB S1 Ag 3/4 = 0.50, rev 7¨ +/-1¨', 154.0),
     ('VMO', 'EXTERIORES', 8, '8', 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 6"+/- 1".', 136.0),
     ('VMO', 'EXTERIORES', 9, '9', 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. Imp', 147.0),
     ('VMO',
      'EXTERIORES',
      10,
      '10',
      'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.45, rev. 6"+/- 1".',
      159.1),
     ('VMO',
      'EXTERIORES',
      11,
      '11',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp',
      186.98),
     ('VMO', 'EXTERIORES', 12, '12', 'Hormigón Fc350 kg/cm2,  Agg 3/8", Temp. 32C, rev. 6"+/- 1', 154.02),
     ('VMO',
      'EXTERIORES',
      13,
      '13',
      'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1".',
      154.02),
     ('VMO', 'EXTERIORES', 14, '14', 'Hormigón 280 kg/cm2, Ag 3/8",T 32C, rev. 7" +/- 1", Fibra', 148.55),
     ('VMO', 'EXTERIORES', 15, '15', 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1"acelerado', 175.0),
     # 2026-10-05: no esta en el documento del cliente. Aparecieron 2 conduces
     # (M700019645/46) sin renglon; precio y clave confirmados por el usuario.
     # La descripcion es la de los conduces, que es contra la que se matchea.
     ('VMO', 'EXTERIORES', 16, '16', 'Mortero fc250, 100% arena, Temp 32C, rev. 6+/-1', 148.11)
]

PRECIOS_VMO = [
    ('5005', None, 'CARGO POR TRABAJO DIA FERIADO', 3.29),
     ('4443', None, 'CARGO POR TRABAJO EN HORARIO NOCTURNO.', 3.29),
     ('403', None, 'RETARDANTE', 7.0),
     ('407', 'EXTERIORES', 'FIBRA', 14.0),
     ('407', 'PODIUM-1-2-3', 'FIBRA', 7.0),
     ('4413', 'EXTERIORES', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 109.0),
     ('4413', 'PATIO DE MANIOBRAS-TRA', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 108.5),
     ('4413', 'CEDIS', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".', 109.0),
     ('44942', 'CEDIS', 'PAVIMENTACION RIGIDA MR-42, T35C', 166.45),  # 2026-10-20, precio del usuario
     ('44510', None, 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 7" +/- 1"', 111.0),
     ('44506', None, 'Hormigón 210,agg 3/4, Temp 35C, rev. 6+/-1', 122.0),
     ('44519', None, 'Hormigón 210 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp', 133.0),
     ('44507', None, 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1"', 133.0),
     ('4415', None, 'Hormigón Fc280 kg/cm2, Agg 3/4", Temp. 32C, rev. 6"+/- 1"', 136.0),
     ('44520', None, 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp', 140.0),
     ('44522', None, 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp', 147.0),
     ('44708', None, 'Hormigón 280 kg/cm2, Ag 3/8",T 32C, rev. 7" +/- 1", Fibra', 148.55),
     ('44521', None, 'Hormigon 250kg/cm2, AMB S1, Ag 3/4",T 32C, a/c= 0.50, rev. 7" +/-1"', 154.0),
     ('44531', None, 'Hormigón Fc350 kg/cm2,  Agg 3/8", Temp. 32C, rev. 6"+/- 1', 154.02),
     ('4419', None, 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1".', 154.02),
     ('44721', None, 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.45, rev. 6"+/- 1"**.', 159.1),
     ('4418', None, 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.45, rev. 6"+/- 1".', 159.1),
     ('402', None, 'IMPERMEABILIZANTE', 12.5),
     ('44508', None, 'Hormigón 250 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1"acelerado', 175.0),
     ('44526', None, 'Pavimentacion rigida MR-43, fibra econom.', 172.47),
     ('44534', None, 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", Fibra.', 142.0),
     ('4496', None, 'Mortero fc250, 100% arena, Temp 32C, rev. 6+/-1', 148.11),
     ('4417',
      None,
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 6"+/- 1".',
      190.12),
     ('4477',
      None,
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp',
      186.98),
     ('44608', None, 'PAVIMENTACION RIGIDA MR32, T35C, Directo', 152.86),
     ('44556', None, 'Hormigón 180 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"', 121.6),
     ('44702', None, 'Hormigón 150 kg/cm2, Ag. ¾”, T 35C, rev. 6”+/-1” imp', 119.0),
     ('44703', None, 'Hormigón 150 kg/cm2, Ag. 3/8”, T 35C, rev. 6”+/-1”', 117.0),
     ('44704', None, 'Hormigón 180 kg/cm2, Ag. 3/4”, T 35C, rev. 6”+/-1” imp', 129.6),
     ('44705', None, 'Hormigón 180 kg/cm2, Ag. 3/8”, T 35C, rev. 6”+/-1”', 127.6),
     ('44713', None, 'Mortero Fc80 kg/cm2, 100% arena, Temp. 35C, rev. 6"+/- 1", imp.', 147.19),
     ('4486',
      None,
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp**',
      186.98)
]

PRECIOS_DOMICEM = [
    ('CAVERNAS', '4413', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1". ', 109.0),
     ('CAVERNAS', '4443', 'CARGO POR TRABAJO EN HORARIO NOCTURNO. ', 3.29),
     ('CAVERNAS', '44506', 'Hormigón 210,agg 3/4, Temp 35C, rev. 6+/-1', 122.0),
     ('CAVERNAS', '44510', 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 7" +/- 1" ', 111.0),
     ('CAVERNAS', '44524', 'Hormigón 280 kg/cm2, Ag 3/8",T 32C, rev. 7" +/- 1", imp', 156.45),
     ('CAVERNAS', '44551', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1" ', 133.0),
     ('CAVERNAS', '44556', 'Hormigón 180 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"     ', 121.6),
     ('CAVERNAS', '44558', 'Hormigón 210 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.     ', 130.0),
     ('CAVERNAS', '44560', 'Hormigón 240 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp. ', 136.3),
     ('CAVERNAS', '44561', 'Hormigón 240 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"        ', 126.3),
     ('CAVERNAS', '44563', 'Hormigón 250 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.     ', 138.0),
     ('CAVERNAS', '44564', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.      ', 145.0),
     ('CAVERNAS',
      '4477',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp  ',
      186.98),
     ('CAVERNAS',
      '44610',
      'FC 350kg/cm2, AMB IIIA, Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp, ac 7 Dias',
      194.07),
     ('CAVERNAS', '5005', 'CARGO POR TRABAJO DIA FERIADO', 3.29),
     ('MACAO 2', '4418', 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.45, rev. 6"+/- 1".  ', 159.1),
     ('MACAO 2', '4419', 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1". ', 154.02),
     ('MACAO 2', '4443', 'CARGO POR TRABAJO EN HORARIO NOCTURNO. ', 3.29),
     ('MACAO 2', '44567', 'DIFERENCIA POR MINIMO (M3) DOMINGOS Y FERIADOS', 154.02),
     ('MACAO 2',
      '4477',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp  ',
      186.98),
     ('MACAO 2', '5005', 'CARGO POR TRABAJO DIA FERIADO', 3.29),
     ('VIVIENDAS', '4413', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1". ', 109.0),
     ('VIVIENDAS', '4443', 'CARGO POR TRABAJO EN HORARIO NOCTURNO. ', 3.29),
     ('VIVIENDAS', '44510', 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 7" +/- 1" ', 111.0),
     ('VIVIENDAS', '44550', 'Hormigón 210 kg/cm2, Ag 3/8",T 35C, rev. 6" +/- 1"  ', 125.56),
     ('VIVIENDAS', '44551', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1" ', 133.0),
     ('VIVIENDAS', '44564', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", imp.      ', 145.0),
     ('VIVIENDAS', '44552', 'Hormigón 280 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1", acelerado', 170.0),
     ('VIVIENDAS', '44567', 'DIFERENCIA POR MINIMO (M3) DOMINGOS Y FERIADOS', 146.33),
     ('VIVIENDAS', '44579', 'Hormigón 280 kg/cm2, Ag 3/8",T 35C, rev. 6" +/- 1"', 143.04),
     ('VIVIENDAS', '5005', 'CARGO POR TRABAJO DIA FERIADO', 3.29),
     ('VIVIENDAS', '44604', 'Mortero Fc80 kg/cm2, 100% arena, Temp. 35C, rev. 6"+/- 1".', 134.69),
     ('VIVIENDAS', '44605', 'Hormigón 280 kg/cm2, Ag 3/8",T 35C, rev. 8" +/- 1"', 147.99),
     ('CIMENTACIONES MACAO II', '4413', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1". ', 108.5),
     ('CIMENTACIONES MACAO II', '4443', 'CARGO POR TRABAJO EN HORARIO NOCTURNO. ', 3.29),
     ('CIMENTACIONES MACAO II',
      '44548',
      'Hormigón Fc350 kg/cm2, AMB. S1, 3/4", T 32C, a/c 0.50, S 10%,  6"+/- 1", antideslave.',
      218.2),
     ('CIMENTACIONES MACAO II', '44567', 'DIFERENCIA POR MINIMO (M3) DOMINGOS Y FERIADOS', 221.29),
     ('CIMENTACIONES MACAO II',
      '44570',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1"',
      191.27),
     ('CIMENTACIONES MACAO II',
      '44600',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/8", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1", imp',
      208.01),
     ('CIMENTACIONES MACAO II',
      '44601',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1" **',
      191.27),
     ('CIMENTACIONES MACAO II',
      '4461',
      'Hormigon 350kg/cm2, AMB S1, Ag 3/4",T 32C, a/c= 0.50, rev. 8" +/-1", S 10%, Imp',
      200.01),
     ('CIMENTACIONES MACAO II', '5005', 'CARGO POR TRABAJO DIA FERIADO', 3.29),
     ('PATIO DE MANIOBRAS-TRB', '4413', 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1". ', 108.5),
     ('PATIO DE MANIOBRAS-TRB',
      '4419',
      'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1". ',
      154.02),
     ('PATIO DE MANIOBRAS-TRB',
      '44570',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1"',
      191.27),
     ('PATIO DE MANIOBRAS-TRB',
      '4477',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp  ',
      186.98),
     ('PATIO DE MANIOBRAS-TRB', '4443', 'CARGO POR TRABAJO DIA FERIADO', 3.29),
     ('MACAO 2',
      '4486',
      'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp**',
      186.98),
     ('MACAO 2', '44721', 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.45, rev. 6"+/- 1"**.', 159.1),
     ('MACAO 2',
      '44600',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/8", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1", imp',
      208.01),
     ('MACAO 2',
      '44570',
      'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1"',
      191.27)
]


def seed(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO catalogo_estimacion "
            "(empresa, fase, orden, clave, descripcion, precio_unitario) VALUES (?,?,?,?,?,?)",
            CATALOGO_ESTIMACION,
        )
        # En SQLite una PK compuesta no vuelve NOT NULL sus columnas: las
        # filas VMO genericas usan fase=NULL y, sin el NOT EXISTS, NULL evita
        # que INSERT OR IGNORE detecte el duplicado en una segunda corrida.
        conn.executemany(
            "INSERT OR IGNORE INTO precios_vmo "
            "(codigo, fase, descripcion, precio_unitario) "
            "SELECT ?,?,?,? WHERE NOT EXISTS ("
            "SELECT 1 FROM precios_vmo WHERE codigo = ? AND fase IS ?"
            ")",
            [(*fila, fila[0], fila[1]) for fila in PRECIOS_VMO],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO precios_domicem "
            "(fase, codigo, descripcion, precio_unitario) VALUES (?,?,?,?)",
            PRECIOS_DOMICEM,
        )
        conn.commit()
        return {
            "catalogo_estimacion": conn.execute("SELECT COUNT(*) FROM catalogo_estimacion").fetchone()[0],
            "precios_vmo": conn.execute("SELECT COUNT(*) FROM precios_vmo").fetchone()[0],
            "precios_domicem": conn.execute("SELECT COUNT(*) FROM precios_domicem").fetchone()[0],
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Siembra catalogo y precios de Estimaciones")
    parser.add_argument("db_path", nargs="?", default=DEFAULT_DB_PATH, help="Ruta de estimaciones.db")
    args = parser.parse_args()
    conteos = seed(args.db_path)
    print(
        "Seed listo: "
        f"catalogo_estimacion={conteos['catalogo_estimacion']}, "
        f"precios_vmo={conteos['precios_vmo']}, "
        f"precios_domicem={conteos['precios_domicem']}"
    )


if __name__ == "__main__":
    main()
