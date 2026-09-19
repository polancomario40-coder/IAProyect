import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import { LOGO_VMO_BASE64 } from '../assets/logoBase64';

const formatearFechaHora = (fecha: any) => {
  if (!fecha) return '-';
  try {
    const d = new Date(fecha);
    if (isNaN(d.getTime())) return String(fecha);
    const pad = (n: number) => n.toString().padStart(2, '0');
    const dia = pad(d.getDate());
    const mes = pad(d.getMonth() + 1);
    const anio = d.getFullYear();
    let horas = d.getHours();
    const minutos = pad(d.getMinutes());
    const ampm = horas >= 12 ? 'PM' : 'AM';
    horas = horas % 12;
    horas = horas ? horas : 12;
    return `${dia}/${mes}/${anio} ${pad(horas)}:${minutos} ${ampm}`;
  } catch {
    return String(fecha);
  }
};

export const generarTicketPDF = async (ticket: any) => {
  let nombreEmpresa = '';
  try {
    const empStorage = localStorage.getItem('empresa');
    if (empStorage) {
      const empObj = JSON.parse(empStorage);
      nombreEmpresa = empObj.empresa || empObj.nombre || '';
    }
  } catch {}
  if (!nombreEmpresa) {
    nombreEmpresa = ticket.empresaNombre || 'VMO CONCRETOS';
  }

  const isoIdent = ticket.isoIdentificador || 'FE-GC-02';
  const isoRev = ticket.isoRevision || '03';

  const div = document.createElement('div');
  div.style.width = '280px';
  div.style.padding = '0px 4px 4px 4px';
  div.style.margin = '0px';
  div.style.boxSizing = 'border-box';
  div.style.backgroundColor = 'white';
  div.style.color = 'black';
  div.style.fontFamily = 'monospace, Arial, sans-serif';
  div.style.fontSize = '15px';
  div.style.lineHeight = '1.25';
  div.style.position = 'fixed';
  div.style.left = '-9999px';
  div.style.top = '0px';
  
  div.innerHTML = `
    <!-- HEADER CON EMPRESA E ISO -->
    <div style="border-bottom: 2px dashed black; padding-bottom: 5px; margin-bottom: 6px; text-align: center;">
      <div style="display: flex; justify-content: flex-end; margin-top: 0; margin-bottom: 2px;">
        <span style="font-size: 11px; font-weight: bold; border: 1px solid black; padding: 1px 4px; border-radius: 2px;">
          ${isoIdent} Rev.: ${isoRev}
        </span>
      </div>
      <div style="text-align: center; margin: 2px 0 4px 0;">
        <img src="data:image/png;base64,${LOGO_VMO_BASE64}" alt="Logo" style="max-height: 48px; max-width: 170px; object-fit: contain; display: inline-block;" />
      </div>
      <h2 style="margin: 1px 0 2px 0; font-size: 18px; font-weight: 900; text-transform: uppercase; letter-spacing: 0.5px;">${nombreEmpresa}</h2>
      <p style="margin: 1px 0; font-size: 13px; font-weight: bold;">AUTORIZACIÓN DE DESPACHO / RECEPCIÓN</p>
    </div>

    <!-- DATOS GENERALES (LABEL ARRIBA / VALOR ABAJO) -->
    <div style="margin-bottom: 6px;">
      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">FECHA:</div>
        <div style="font-size: 15px; font-weight: bold;">${formatearFechaHora(ticket.fechaImpresion)}</div>
      </div>

      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">ID CONDUCE:</div>
        <div style="font-size: 16px; font-weight: bold; word-break: break-word;">${ticket.conduceTransporte || ticket.conduce}</div>
      </div>

      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">PLANTA DE DESTINO:</div>
        <div style="font-size: 15px; font-weight: bold; word-break: break-word;">${ticket.almacen || ticket.idAlmacen || '-'}</div>
      </div>

      ${ticket.conduceTransporte ? `
      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">CONDUCE PROVEEDOR:</div>
        <div style="font-size: 15px; font-weight: bold; word-break: break-word;">${ticket.conduce}</div>
      </div>` : ''}

      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">NOMBRE DE SUPLIDOR:</div>
        <div style="font-size: 15px; font-weight: bold; word-break: break-word;">${ticket.suplidor || '-'}</div>
      </div>

      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">NOMBRE DEL CONDUCTOR:</div>
        <div style="font-size: 15px; font-weight: bold; word-break: break-word;">${ticket.nombreChofer || '-'}</div>
      </div>

      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">TRANSPORTISTA / FICHA:</div>
        <div style="font-size: 15px; font-weight: bold; word-break: break-word;">${ticket.transportista || '-'}</div>
      </div>

      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">MATRÍCULA (PLACA):</div>
        <div style="font-size: 15px; font-weight: bold; word-break: break-word;">${ticket.placa || '-'}</div>
      </div>
    </div>

    <!-- INFORMACIÓN DEL MATERIAL (SOPORTE MULTI-PRODUCTO) -->
    <div style="border-top: 2px dashed black; padding-top: 6px; margin-bottom: 6px;">
      <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase; margin-bottom: 4px;">PRODUCTO(S) / MATERIAL(ES):</div>
      ${ticket.productos && ticket.productos.length > 0 ? 
        ticket.productos.map((prod: any, idx: number) => `
          <div style="margin: 4px 0; padding-bottom: 4px; ${idx < ticket.productos.length - 1 ? 'border-bottom: 1px dotted #aaa;' : ''}">
            <div style="font-size: 14px; font-weight: bold; word-break: break-word;">
              ${ticket.productos.length > 1 ? `${idx + 1}. ` : ''}${prod.producto || '-'}
            </div>
            <div style="margin: 2px 0; display: flex; justify-content: space-between; align-items: baseline;">
              <span style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">CANTIDAD:</span>
              <span style="font-size: 16px; font-weight: 900;">
                ${prod.cantidadRecibida != null ? `${prod.cantidadRecibida} ${prod.idUnidad || 'Mts'}` : (prod.cantidadDeclarada != null ? `${prod.cantidadDeclarada} ${prod.idUnidad || 'Mts'}` : '-')}
              </span>
            </div>
            ${prod.ordenNumero ? `
              <div style="font-size: 11px; font-weight: bold; color: #2563eb;">OC ASIGNADA: #${prod.ordenNumero}</div>
            ` : ''}
          </div>
        `).join('')
      : `
        <div style="margin: 3px 0;">
          <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">TIPO DE MATERIAL:</div>
          <div style="font-size: 15px; font-weight: bold; word-break: break-word;">${ticket.producto || '-'}</div>
        </div>

        <div style="margin: 4px 0; display: flex; justify-content: space-between; align-items: baseline;">
          <span style="font-size: 12px; font-weight: bold; color: #444; text-transform: uppercase;">CANTIDAD:</span>
          <span style="font-size: 18px; font-weight: 900;">${ticket.cantidadRecibida ? `${ticket.cantidadRecibida} ${ticket.idUnidad || 'Mts'}` : (ticket.cantidadDeclarada ? `${ticket.cantidadDeclarada} ${ticket.idUnidad || 'Mts'}` : '-')}</span>
        </div>
      `}

      ${ticket.fechaRecepcion ? `
      <div style="margin: 3px 0; display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">RECEPCIÓN:</span>
        <span style="font-size: 13px; font-weight: bold;">${formatearFechaHora(ticket.fechaRecepcion)}</span>
      </div>` : ''}

      <div style="margin: 3px 0; display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">ESTADO:</span>
        <span style="font-size: 13px; font-weight: bold;">${ticket.status || '-'}</span>
      </div>

      ${ticket.ordenNumero && (!ticket.productos || ticket.productos.length <= 1) ? `
      <div style="margin: 3px 0; display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">OC ASIGNADA:</span>
        <span style="font-size: 13px; font-weight: bold;">#${ticket.ordenNumero}</span>
      </div>` : ''}

      ${ticket.notas ? `
      <div style="margin: 3px 0;">
        <div style="font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;">NOTAS:</div>
        <div style="font-size: 13px; font-weight: normal; word-break: break-word;">${ticket.notas}</div>
      </div>` : ''}
    </div>

    <!-- FIRMAS DE AUTORIZACIÓN -->
    <div style="border-top: 2px dashed black; margin-top: 8px; padding-top: 5px;">
      <p style="margin: 0 0 5px 0; font-size: 12px; font-weight: bold; text-align: center;">FIRMAS DE AUTORIZACIÓN</p>
      <div style="display: flex; justify-content: space-between; gap: 10px; margin-top: 3px;">
        <div style="flex: 1; text-align: center;">
          <div style="height: 42px;"></div>
          <div style="border-bottom: 1px solid black; margin-bottom: 3px;"></div>
          <p style="margin: 0; font-size: 11px; font-weight: bold;">Firma Autorizada</p>
          <p style="margin: 0; font-size: 10px; color: #333; word-break: break-word;">${ticket.usuarioRecepcion || ''}</p>
        </div>
        <div style="flex: 1; text-align: center;">
          <div style="height: 42px; display: flex; align-items: center; justify-content: center;">
            ${ticket.firmaDigitalBase64 
              ? `<img src="data:image/png;base64,${ticket.firmaDigitalBase64}" style="max-height: 40px; max-width: 120px; object-fit: contain;" />` 
              : ''}
          </div>
          <div style="border-bottom: 1px solid black; margin-bottom: 3px;"></div>
          <p style="margin: 0; font-size: 11px; font-weight: bold;">Firma del Chofer</p>
          <p style="margin: 0; font-size: 10px; color: #333; word-break: break-word;">${ticket.nombreChofer || ''}</p>
        </div>
      </div>
    </div>

    <!-- PIE DE FORMULARIO -->
    <div style="text-align: center; margin-top: 10px; border-top: 1px dotted black; padding-top: 5px;">
      <p style="margin: 0; font-size: 10px; font-weight: bold; letter-spacing: 0.2px;">NO DESPACHAR SIN LA ENTREGA DE ESTE FORMULARIO</p>
      <p style="margin: 2px 0 0 0; font-size: 10px;">** Conserve este ticket **</p>
    </div>
  `;

  document.body.appendChild(div);

  try {
    const canvas = await html2canvas(div, { 
      scale: 2,
      scrollX: 0,
      scrollY: 0,
      useCORS: true,
      logging: false
    });
    const imgData = canvas.toDataURL('image/png');
    
    // Formato ticket con altura dinámica exacta al milímetro para evitar desperdicio de papel
    const pdfWidth = 75; // Ancho imprimible térmico estándar de 80mm
    const calculatedHeight = (canvas.height * pdfWidth) / canvas.width;
    const pdfHeight = Math.ceil(calculatedHeight);

    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: [pdfWidth, pdfHeight]
    });
    
    pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, calculatedHeight);
    
    // Enviar a imprimir automáticamente
    pdf.autoPrint();
    
    // Blob url e imprimir mediante un iframe oculto para evitar bloqueos de popups
    const blob = pdf.output('bloburl');
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = blob.toString();
    document.body.appendChild(iframe);
    
    // Limpiar el iframe después de 10 segundos
    setTimeout(() => {
      if (document.body.contains(iframe)) {
        document.body.removeChild(iframe);
      }
    }, 10000);
  } finally {
    document.body.removeChild(div);
  }
};
