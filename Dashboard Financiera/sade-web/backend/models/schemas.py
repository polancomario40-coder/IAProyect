"""
schemas.py — Pydantic models para validación y serialización de respuestas
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
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
    nombreCliente: str
    fechaPrestamo: date
    fechaConsulta: datetime
    estado: str  # "AL DIA" | "ATRASADO"

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

    # Meta
    cuotasVencidas: int
    tasaInteres: Optional[Decimal] = None
    creador: Optional[str] = None
    tipoPrestamo: Optional[str] = None


class Cuota(BaseModel):
    numCuota: int
    idCuota: str  # UNIQUEIDENTIFIER (GUID)
    fecha: date
    balance: Decimal
    capital: Decimal
    interes: Decimal
    mora: Decimal
    estadoCuota: str  # "PAGADA" | "VENCIDA" | "PENDIENTE"


class Recibo(BaseModel):
    numeroPago: int
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
    clasificacion: str = 'NUEVO'


class ClientesStats(BaseModel):
    totalClientes: int
    nuevos: int
    reenganchados: int
    enMora: int
    problematicos: int
    alDia: int
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
