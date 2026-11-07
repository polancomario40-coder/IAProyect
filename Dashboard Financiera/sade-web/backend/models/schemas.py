"""
schemas.py — Pydantic models para validación y serialización de respuestas
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Union
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

class DashboardKPIs(BaseModel):
    # Cartera Activa
    capitalPendiente: Decimal
    capitalOriginal: Decimal
    totalPrestamos: int

    # Cobros del Mes
    capitalCobradoMes: Decimal
    interesCobradoMes: Decimal
    moraCobradaMes: Decimal
    totalCobradoMes: Decimal
    recibosMes: int

    # Cartera Vencida
    prestamosAtrasados: int
    tasaMora: Decimal

    # Moras e Intereses pendientes
    interesesPendientes: Decimal
    morasPendientes: Decimal

    # Periodo
    periodoInicio: date
    periodoFin: date
    generadoEn: datetime


class CobrosporMes(BaseModel):
    mesFecha: date
    mesEtiqueta: str
    capitalCobrado: Decimal
    interesCobrado: Decimal
    moraCobrada: Decimal
    totalCobrado: Decimal
    cantidadRecibos: int


class DashboardResponse(BaseModel):
    kpis: DashboardKPIs
    cobrosporMes: list[CobrosporMes]


# ─────────────────────────────────────────────
# ESTADO DE PRÉSTAMO
# ─────────────────────────────────────────────

class EncabezadoPrestamo(BaseModel):
    numeroPrestamo: str
    idCliente: Optional[int] = None
    nombreCliente: str
    fechaPrestamo: date
    fechaConsulta: datetime
    estado: str  # "AL DIA" | "ATRASADO" | "SALDADO"

    # Bloque Inicial
    capitalInicial: Decimal
    interesInicial: Decimal
    totalInicial: Decimal

    # Bloque Pagado
    capitalPagado: Decimal
    interesPagado: Decimal
    moraPagada: Decimal
    totalPagado: Decimal

    # Bloque Balance
    capitalBalance: Decimal
    interesBalance: Decimal
    moraBalance: Decimal
    totalBalance: Decimal

    # Bloque Vencido
    capitalVencido: Decimal
    interesVencido: Decimal
    moraVencida: Decimal
    totalVencido: Decimal

    # Proyección para Saldar Hoy
    montoSaldarHoy: Optional[Decimal] = None
    diasDesdeVencimiento: Optional[int] = None
    ultimoVencimiento: Optional[datetime] = None

    # Meta
    cuotasVencidas: Optional[int] = 0
    tasaInteres: Optional[Decimal] = None
    creador: Optional[str] = None
    tipoPrestamo: Optional[str] = None


class Cuota(BaseModel):
    numCuota: int
    idCuota: str  # UNIQUEIDENTIFIER (GUID) o string id
    fecha: date
    balance: Decimal
    capital: Decimal
    interes: Decimal
    mora: Decimal
    estadoCuota: Optional[str] = 'PENDIENTE'
    estado: Optional[str] = None


class Recibo(BaseModel):
    numeroPago: Union[int, str]
    fecha: date
    totalPagado: Decimal
    capital: Decimal
    interes: Decimal
    mora: Decimal
    usuario: Optional[str] = None
    observacion: Optional[str] = None


class ConteosPrestamo(BaseModel):
    totalCuotas: int
    totalRecibos: int


class EstadoPrestamoResponse(BaseModel):
    encabezado: EncabezadoPrestamo
    cuotas: list[Cuota]
    recibos: list[Recibo]
    conteos: ConteosPrestamo


# ─── Clientes ──────────────────────────────────────────────
class ClienteResumen(BaseModel):
    idCliente: int
    nombreCompleto: str
    cedula: Optional[str] = None
    telefono: Optional[str] = None
    correo: Optional[str] = None
    oficina: Optional[str] = None
    fechaRegistro: Optional[date] = None
    empresa: Optional[str] = None
    cargoEmpresa: Optional[str] = None
    salario: Optional[Decimal] = None
    creador: Optional[str] = None
    gestor: Optional[str] = None
    sexo: Optional[str] = None
    esProblematico: Optional[bool] = None
    banco: Optional[str] = None
    cuentaBancaria: Optional[str] = None
    totalPrestamos: int = 0
    prestamosActivos: int = 0
    primerPrestamo: Optional[datetime] = None
    ultimoPrestamo: Optional[datetime] = None
    montoHistorico: Optional[Decimal] = None
    numeroPrestamo: Optional[str] = None
    montoActual: Optional[Decimal] = None
    tasa: Optional[float] = None
    fechaPrestamo: Optional[datetime] = None
    vencimiento: Optional[datetime] = None
    capitalPagado: Optional[Decimal] = None
    balanceActual: Optional[Decimal] = None
    balanceCapital: Optional[Decimal] = None
    montoSaldarHoy: Optional[Decimal] = None
    clasificacion: str = 'NUEVO'
    estadoCartera: Optional[str] = 'ACTIVO'

    # Referencias personales
    nombreRef1: Optional[str] = None
    parentescoRef1: Optional[str] = None
    telRef1: Optional[str] = None
    dirRef1: Optional[str] = None
    nombreRef2: Optional[str] = None
    parentescoRef2: Optional[str] = None
    telRef2: Optional[str] = None
    dirRef2: Optional[str] = None


class ClientesStats(BaseModel):
    totalClientes: int
    totalClientesGlobal: Optional[int] = None
    totalFiltrados: Optional[int] = None
    nuevos: int
    reenganchados: int
    enMora: int
    problematicos: int
    alDia: int
    cancelados: Optional[int] = 0
    montoTotalCartera: Decimal
    balanceTotalPendiente: Decimal
    paginaActual: int
    porPagina: int
    totalPaginas: int


class EmpresaDistribucion(BaseModel):
    empresa: str
    totalClientes: int
    nuevos: int
    reenganchados: int
    enMora: int
    cartera: Decimal


class ClientesResponse(BaseModel):
    stats: ClientesStats
    clientes: List[ClienteResumen]
    porEmpresa: List[EmpresaDistribucion]
    oficinas: List[str]


# ─── Historial y Perfil Integral del Cliente ──────────────
class PrestamoHistoricoItem(BaseModel):
    numeroPrestamo: str
    montoOriginal: Decimal
    interesOriginal: Decimal
    totalOriginal: Decimal
    tasa: float
    fechaPrestamo: date
    fechaVencimiento: Optional[date] = None
    idEstado: int
    estado: str  # "ACTIVO" | "SALDADO"
    balanceTotal: Decimal
    balanceCapital: Decimal
    capitalPagado: Decimal
    interesPagado: Decimal
    totalPagado: Decimal
    creador: Optional[str] = None
    ultimoVencimiento: Optional[datetime] = None
    montoSaldarHoy: Decimal


class ClienteDetalle(BaseModel):
    idCliente: int
    nombreCompleto: str
    cedula: Optional[str] = None
    telefono: Optional[str] = None
    correo: Optional[str] = None
    direccion: Optional[str] = None
    oficina: Optional[str] = None
    fechaRegistro: Optional[date] = None
    empresa: Optional[str] = None
    cargoEmpresa: Optional[str] = None
    salario: Optional[Decimal] = None
    creador: Optional[str] = None
    sexo: Optional[str] = None
    esProblematico: Optional[bool] = None
    banco: Optional[str] = None
    cuentaBancaria: Optional[str] = None
    nombreRef1: Optional[str] = None
    parentescoRef1: Optional[str] = None
    telRef1: Optional[str] = None
    dirRef1: Optional[str] = None
    nombreRef2: Optional[str] = None
    parentescoRef2: Optional[str] = None
    telRef2: Optional[str] = None
    dirRef2: Optional[str] = None
    totalPrestamos: int = 0
    prestamosActivos: int = 0
    clasificacionGlobal: str = 'NUEVO'


class ClienteHistorialResponse(BaseModel):
    cliente: ClienteDetalle
    prestamos: List[PrestamoHistoricoItem]


# ─── Reportes Analíticos (Plantillas Excel / PDF) ─────────
class ReporteDetalleClienteItem(BaseModel):
    idCliente: int
    clasificacion: str
    nombreCliente: str
    cedula: Optional[str] = None
    empresa: Optional[str] = None
    numeroPrestamo: Optional[str] = None
    montoPrestamo: Decimal
    capitalPagado: Decimal = Decimal('0.00')
    balanceAntesCobro: Decimal
    capitalCobradoQuincena: Decimal
    interesCobradoQuincena: Decimal
    capitalActualAdeudado: Decimal = Decimal('0.00')
    totalCobradoQuincena: Decimal
    balanceActual: Decimal
    tasa: float
    fechaPrestamo: Optional[datetime] = None
    comentario: Optional[str] = None


class ReporteDetalleClientesTotales(BaseModel):
    totalRegistros: int
    totalMontoPrestamo: Decimal
    totalCapitalPagado: Decimal = Decimal('0.00')
    totalBalanceAntesCobro: Decimal
    totalCapitalCobradoQuincena: Decimal
    totalInteresCobradoQuincena: Decimal
    totalCapitalActualAdeudado: Decimal = Decimal('0.00')
    totalCobradoQuincena: Decimal
    totalBalanceActual: Decimal
    tasaPromedio: float
    periodoDesde: Optional[date] = None
    periodoHasta: Optional[date] = None
    quincenaDesde: Optional[date] = None
    quincenaHasta: Optional[date] = None


class ReporteDetalleClientesResponse(BaseModel):
    totales: ReporteDetalleClientesTotales
    filas: List[ReporteDetalleClienteItem]


class ReporteConsolidadoCarteraItem(BaseModel):
    cartera: str
    balanceCapitalColocado: Decimal
    capitalClientesInactivosCancelados: Decimal
    capitalActivo: Decimal
    clientesActivos: int
    clientesInactivos: int
    capitalCobradoQuincena: Decimal
    interesCobradoQuincena: Decimal
    tasa: float


class ReporteConsolidadoCarteraTotales(BaseModel):
    totalCarteras: int
    totalBalanceCapitalColocado: Decimal
    totalCapitalInactivosCancelados: Decimal
    totalCapitalActivo: Decimal
    totalClientesActivos: int
    totalClientesInactivos: int
    totalCapitalCobradoQuincena: Decimal
    totalInteresCobradoQuincena: Decimal
    tasaPromedioPonderada: float
    fechaCorte: Optional[date] = None
    quincenaDesde: Optional[date] = None
    quincenaHasta: Optional[date] = None


class ReporteConsolidadoCarteraResponse(BaseModel):
    totales: ReporteConsolidadoCarteraTotales
    filas: List[ReporteConsolidadoCarteraItem]

