import React, { useRef, useState, useEffect } from 'react';
import SignatureCanvas from 'react-signature-canvas';
import { Eraser, Check } from 'lucide-react';
import './FirmaCanvas.css';

interface Props {
  onFirma: (base64: string) => void;
}

const FirmaCanvas: React.FC<Props> = ({ onFirma }) => {
  const sigCanvas = useRef<SignatureCanvas>(null);
  const [tieneFirma, setTieneFirma] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [canvasDimensions, setCanvasDimensions] = useState({ width: 500, height: 200 });

  // Ajustar el tamaño del canvas al contenedor (útil para móviles)
  useEffect(() => {
    const resizeCanvas = () => {
      if (containerRef.current) {
        setCanvasDimensions({
          width: containerRef.current.offsetWidth,
          height: 200
        });
      }
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  }, []);

  const handleEnd = () => {
    if (sigCanvas.current && !sigCanvas.current.isEmpty()) {
      setTieneFirma(true);
      // Guardar PNG base64 transparente
      const base64 = sigCanvas.current.getTrimmedCanvas().toDataURL('image/png').split(',')[1];
      onFirma(base64);
    }
  };

  const clear = () => {
    sigCanvas.current?.clear();
    setTieneFirma(false);
    onFirma('');
  };

  return (
    <div className="firma-container" ref={containerRef}>
      <label className="firma-label">Firma del Transportista / Chofer</label>
      
      <div className="firma-wrapper">
        <SignatureCanvas
          ref={sigCanvas}
          penColor="blue"
          canvasProps={{
            width: canvasDimensions.width,
            height: canvasDimensions.height,
            className: 'firma-canvas'
          }}
          onEnd={handleEnd}
        />
        {!tieneFirma && <div className="firma-placeholder">Firme aquí</div>}
      </div>

      <div className="firma-controles">
        <button type="button" className="btn-limpiar" onClick={clear}>
          <Eraser size={16} /> Limpiar
        </button>
        {tieneFirma && <span className="firma-ok"><Check size={16} /> Firma registrada</span>}
      </div>
    </div>
  );
};

export default FirmaCanvas;
