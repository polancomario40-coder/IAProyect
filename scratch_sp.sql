

CREATE procedure [dbo].[svCuadreUsuario] 
--declare
 @desde datetime,    
 @hasta datetime,    
 @usuario varchar(30), 
 @Sucursal varchar(30)   
as    
    
--set @desde = '20181001'
--set @hasta = '20181029'
--set @usuario = null
--set @sucursal = null

select   1 orden,lower(f.usuario) as Usuario,    
	 f.idfactura,    
	 'Factura' as Registro,
	 f.factura as Numero,    
	 case when f.Cancelado = 1 Then 'ANULADA' Else f.Cliente End As Cliente,  
	 f.fecha,    
	 m.Moneda,    
	 case when f.cancelado = 1 and f.Credito = 0 then 0.00 else isnull(fc.Efectivo,0.00) end as Efectivo,    
	 case when f.cancelado = 1 and f.Credito = 0 then 0.00 else isnull(fc.Tarjeta,0.00)  end as Tarjeta,    
	 case when f.cancelado = 1 and f.Credito = 0 then 0.00 else isnull(fc.Cheque,0.00)   end as Cheque,    
	 case when f.cancelado = 1 and f.Credito = 0 then 0.00 else isnull(fc.Otros,0.00)    end as Otros,
	 case when f.Cancelado = 0 and f.Credito = 1 then isnull(f.Total,0.00) end as Credito,
	 case when f.Cancelado = 0 then isnull(f.Total,0.00) end as Factura,
	 0.00 as Recibos,     
	 0.00 as Gastos
from     
  factura f     
  left join facturaCobro fc on f.idfactura = fc.idfactura    
  join moneda m on f.idmoneda = m.idmoneda    
where f.fecha between @desde and @hasta and (@sucursal is null or f.idAlmacen like '%'+@sucursal)
      and (@usuario is null or f.usuario = @usuario)  
	  
	    
union all


select 2 orden, lower(f.usuario) as Usuario,
	f.idRecibo as idfactura,
	'Recibo' as Registro,
	f.Recibo as Numero, 
	case when f.Cancelado = 1 then 'ANULADO' else f.Cliente end as Cliente,
	f.Fecha,
	m.Moneda,
	--0.00 as Efectivo,    
	--0.00 as Tarjeta,    
	--0.00 as Cheque,    
	--0.00 as Otros,
	--0.00 as Credito,
	 case when f.cancelado = 0 and f.idPagoForma='Efectivo' then Valor else 0.00 end as Efectivo,    
	 case when f.cancelado = 0 and f.idPagoForma='Tarjeta' then Valor else 0.00 end as Tarjeta,    
	 case when f.cancelado = 0 and f.idPagoForma='Cheque' then Valor else 0.00 end as Cheque,    
	 case when f.cancelado = 0 and f.idPagoForma >'Otros' then Valor else 0.00 end as Otros,
	 case when f.cancelado = 0 and f.idPagoForma='Credito' then Valor else 0.00 end Credito,
	 0.00 as Factura,     
	 case when f.Cancelado = 1 then 0.00 else f.Valor end as Recibos, 
	 0.00 as Gastos
from recibo f join Moneda m on f.idMoneda = m.idMoneda 
where f.Fecha between @desde and @hasta  and (@sucursal is null or f.idSucursal  like '%'+@sucursal  )
      and (@usuario is null or f.Usuario = @usuario) 



union all


select 3 as orden, '' as Usuario,
	 null as idFactura,    
	 'Gastos' as Registro,
	 gd.Descripcion as Numero,    
	 case when g.Cancelado = 1 Then 'ANULADA' Else gd.referencia End As Cliente,  
	 g.fecha,    
	 m.Moneda,    
	 0.00 efectivo, --case when g.cancelado = 0 and gd.idPagoForma=1 then Importe else 0.00 end as Efectivo,    
	 0.00 targeta, --case when g.cancelado = 0 and gd.idPagoForma=3 then Importe else 0.00 end as Tarjeta,    
	 0.00 cheque, --case when g.cancelado = 0 and gd.idPagoForma=2 then Importe else 0.00 end as Cheque,    
	 0.00 otros, --case when g.cancelado = 0 and gd.idPagoForma >4 then Importe else 0.00 end as Otros,
	 0.00 otros, --case when g.cancelado = 0 and gd.idPagoForma=4 then Importe else 0.00 end Credito,
	 0.00 as Factura,     
	 0.00 as Recibos,
	 case when g.cancelado = 0  then Importe else 0.00 end as Gastos          
from     
  bcoGastosMenores g
  join bcoGastosMenoresdet gd on g.GUIDDocumento = gd.GUIDDocumento    
  left join moneda m on gd.idmoneda = m.idmoneda    
where Fecha between @desde and @hasta and (@sucursal is null or gd.centrocosto like '%'+@sucursal) 
	    and (@usuario is null or g.Usuario = @usuario) 	  
order by 1
    return 0  
	


