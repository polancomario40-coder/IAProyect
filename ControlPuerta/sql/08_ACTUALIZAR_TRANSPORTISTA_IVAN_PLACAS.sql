-- ==========================================================================
-- SCRIPT DE ACTUALIZACION DE PLACAS Y TRANSPORTISTA (TRANSPORTE IVAN)
-- Origen: C:\Users\soporte\Downloads\Detalle transportistas agregados.xlsx
-- Fecha: 2026-11-04 11:45:07
-- ==========================================================================
SET NOCOUNT ON;
BEGIN TRANSACTION;

CREATE TABLE #TmpImport (
    Transportista VARCHAR(100),
    Vehiculo      VARCHAR(100),
    Placa         VARCHAR(20),
    Capacidad     DECIMAL(18,4)
);

INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000018', 27.85);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000444', 28.11);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000476', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000936', 25.23);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F001718', 27.86);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002267', 27.07);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002659', 27.04);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002775', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003032', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003164', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003227', 28.48);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003264', 29.9);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004106', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005362', 26.6);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005454', 26.18);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005656', 26.13);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005893', 26.07);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F006045', 28.86);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F006370', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F007391', 26.13);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F007425', 25.21);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F007451', 26.94);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F007535', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F007541', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F008487', 29);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F008839', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F009256', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F009679', 28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011333', 26.16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011359', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011412', 28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011809', 25);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F012306', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F012891', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F013686', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F014418', 28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015890', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015946', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F016315', 27.17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F017059', 27.5);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F017172', 26.12);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L060609', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L065240', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L121952', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L181438', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L255084', 16.9);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L310840', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L344064', 25.15);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L345178', 16.76);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L352930', 17.5);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L376014', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L378437', 16.5);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L423433', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L432318', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L434493', 18.32);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S000560', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S004286', 16.8);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S005198', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S005924', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S007957', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S008190', 16.99);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S009247', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S010455', 16.8);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S011031', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S011044', 17.6);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014679', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014726', 18.28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S015539', 17.62);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S015618', 16.82);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S015756', 16.67);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S015787', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S016756', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S021435', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S024746', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000282', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000307', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000425', 27.43);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000443', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000553', 26.2);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F000966', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F001046', 29.29);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F001521', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F001538', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F001621', 27.17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F001655', 26.79);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F001833', 24.82);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002181', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002293', 27.35);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002439', 25.88);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002443', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002767', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F002977', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003007', 26.02);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003074', 28.31);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003103', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003639', 25.98);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003778', 26.67);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003988', 25.46);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F003999', 28.4);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004016', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004029', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004096', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004098', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004344', 25);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004482', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004760', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F004811', 27.64);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005139', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005312', 18);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005484', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005556', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005582', 26.52);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005583', 25.54);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005858', 26.52);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005872', 26.86);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005891', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F005969', 27.35);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F006228', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F006299', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F006617', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F007396', 26.6);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F008022', 25);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F008703', 26.69);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F008762', 25.21);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F008981', 30);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F009406', 24.14);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F009608', 24);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F009997', 28.04);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F010420', 27.6);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F010436', 28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F010458', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F010461', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F010726', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F010786', 24.82);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F010827', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011366', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011459', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011639', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011838', 26.48);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011839', 26.48);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011900', 25.42);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F011905', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F012047', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F012224', 29);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F013366', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F013619', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F013873', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F014012', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F014086', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F014151', 26.65);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015047', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015141', 26.65);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015176', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015407', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015412', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015497', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015923', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015925', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F015966', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F016093', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F016303', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F016604', 23.87);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F017503', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F017583', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F017805', 28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F017904', 25.44);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F018434', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F018821', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F018882', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F019212', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F019381', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F019842', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F021284', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F021588', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'F021854', 27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volqueta', 'FC-1164', 26);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L052039', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L060300', 16.09);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L060860', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L133451', 16.8);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L146348', 16.8);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L154822', 15.4);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L181632', 17.23);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L185866', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L190188', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L194459', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L215314', 17.93);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L225914', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L227087', 17.36);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L232348', 17.18);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L233636', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L243930', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L251491', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L266762', 17.5);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L275007', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L278094', 26.88);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L283195', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L291324', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L302401', 18.5);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L302402', 26.28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L320442', 16.33);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L323259', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L391429', 19.22);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L401087', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L411830', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L435587', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L451002', 17.4);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L475878', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L487810', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'L518362', 17.3);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'PP125778', 28.9);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'PP610820', 23);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S002929', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S004874', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S006281', 17.31);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S007180', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S008124', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S009047', 16.27);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S009170', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S009341', 17.52);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S010147', 18.28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S010804', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S011053', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S011210', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S011291', 18.67);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S012092', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S012301', 19.95);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S012637', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S013726', 17.84);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014342', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014775', 16);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014800', 17.34);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014928', 16.28);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014935', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S014954', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S015629', 17.71);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S015635', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S017713', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S021959', 17.7);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S024918', 17);
INSERT INTO #TmpImport VALUES ('Ivan', 'Volteo', 'S025433', 17.7);

-- 1. Actualizar registros existentes en lgTransportistaEquipo
UPDATE e
SET e.idTransportista     = '15', -- TRANSPORTE IVAN
    e.TransportistaEquipo = CASE WHEN ISNULL(t.Vehiculo, '') = '' THEN e.TransportistaEquipo ELSE t.Vehiculo END,
    e.Capacidad           = CASE WHEN t.Capacidad > 0 THEN t.Capacidad ELSE e.Capacidad END,
    e.Status              = 'ACTIVO',
    e.idUnidad            = ISNULL(e.idUnidad, 'M3')
FROM lgTransportistaEquipo e
INNER JOIN #TmpImport t ON UPPER(LTRIM(RTRIM(e.PlacaNo))) = t.Placa;

PRINT 'Equipos actualizados: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

-- 2. Insertar registros que no existen en lgTransportistaEquipo
INSERT INTO lgTransportistaEquipo (
    idTransportistaEquipo,
    TransportistaEquipo,
    idTransportista,
    PlacaNo,
    PlacaVence,
    Status,
    Capacidad,
    idUnidad
)
SELECT
    NEWID(),
    ISNULL(t.Vehiculo, 'VOLQUETA'),
    '15', -- TRANSPORTE IVAN
    t.Placa,
    '2035-12-31',
    'ACTIVO',
    t.Capacidad,
    'M3'
FROM #TmpImport t
WHERE NOT EXISTS (
    SELECT 1 FROM lgTransportistaEquipo e
    WHERE UPPER(LTRIM(RTRIM(e.PlacaNo))) = t.Placa
);

PRINT 'Equipos insertados: ' + CAST(@@ROWCOUNT AS VARCHAR(10));

DROP TABLE #TmpImport;
COMMIT TRANSACTION;
PRINT 'Migracion completada exitosamente.';
