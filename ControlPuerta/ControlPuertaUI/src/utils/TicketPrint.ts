import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

export const generarTicketPDF = async (ticket: any) => {
  const div = document.createElement('div');
  div.style.width = '300px';
  div.style.padding = '20px';
  div.style.backgroundColor = 'white';
  div.style.color = 'black';
  div.style.fontFamily = 'monospace';
  div.style.fontSize = '12px';
  div.style.position = 'absolute';
  div.style.top = '-9999px';
  
  div.innerHTML = `
    <div style="text-align: center; border-bottom: 1px dashed black; padding-bottom: 10px; margin-bottom: 10px;">
      <h2 style="margin: 0;">SADE ERP</h2>
      <p style="margin: 5px 0;">Control de Puerta - Ticket</p>
    </div>
    <div style="margin-bottom: 10px;">
      <p style="margin: 3px 0;"><strong>Fecha:</strong> ${new Date(ticket.fechaImpresion).toLocaleString()}</p>
      <p style="margin: 3px 0;"><strong>Conduce:</strong> ${ticket.conduce}</p>
      <p style="margin: 3px 0;"><strong>Placa:</strong> ${ticket.placa}</p>
      <p style="margin: 3px 0;"><strong>Transp:</strong> ${ticket.transportista}</p>
      <p style="margin: 3px 0;"><strong>Chofer:</strong> ${ticket.nombreChofer}</p>
    </div>
    <div style="border-top: 1px dashed black; padding-top: 10px;">
      <p style="margin: 3px 0;"><strong>Producto:</strong> ${ticket.producto}</p>
      <p style="margin: 3px 0;"><strong>Entrada:</strong> ${new Date(ticket.fechaEntrada).toLocaleString()}</p>
      ${ticket.fechaRecepcion ? `<p style="margin: 3px 0;"><strong>Recepción:</strong> ${new Date(ticket.fechaRecepcion).toLocaleString()}</p>` : ''}
      <p style="margin: 3px 0;"><strong>Estado:</strong> ${ticket.status}</p>
      ${ticket.ordenNumero ? `<p style="margin: 3px 0;"><strong>OC Asignada:</strong> ${ticket.ordenNumero}</p>` : ''}
    </div>
    <div style="text-align: center; margin-top: 20px;">
      <p style="margin: 0; font-size: 10px;">** Conserve este ticket **</p>
    </div>
  `;

  document.body.appendChild(div);

  try {
    const canvas = await html2canvas(div, { scale: 2 });
    const imgData = canvas.toDataURL('image/png');
    
    // Formato ticket 80mm
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: [80, 150]
    });
    
    const imgProps = pdf.getImageProperties(imgData);
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
    
    pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
    
    // Enviar a imprimir automáticamente
    pdf.autoPrint();
    
    // Blob url y abrir en nueva pestaña para imprimir
    const blob = pdf.output('bloburl');
    window.open(blob, '_blank');
  } finally {
    document.body.removeChild(div);
  }
};
