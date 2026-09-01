import React, { useRef, useState } from 'react';
import Webcam from 'react-webcam';
import { Camera, Upload, RotateCcw, Check } from 'lucide-react';
import './CamaraCaptura.css';

interface Props {
  onCaptura: (base64: string, mimeType: string) => void;
  label?: string;
  /** Modo compacto: muestra solo íconos de cámara/subir sin label ni preview grande */
  soloBoton?: boolean;
  /** Prop semántica (no altera lógica) */
  ocr?: boolean;
}

/**
 * CamaraCaptura
 * Permite capturar una imagen desde la cámara del dispositivo
 * o subir un archivo desde el sistema de archivos.
 * Devuelve la imagen como base64 al componente padre.
 */
const CamaraCaptura: React.FC<Props> = ({ onCaptura, label = 'Capturar imagen', soloBoton = false }) => {
  const webcamRef = useRef<Webcam>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [modo, setModo] = useState<'idle' | 'camara' | 'preview'>('idle');
  const [preview, setPreview] = useState<string | null>(null);
  const [camaraDisponible, setCamaraDisponible] = useState(true);

  // Capturar desde cámara
  const capturarFoto = () => {
    const img = webcamRef.current?.getScreenshot({ width: 1280, height: 720 });
    if (img) {
      setPreview(img);
      setModo('preview');
      onCaptura(img.split(',')[1], 'image/jpeg');
    }
  };

  // Subir desde archivo
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      const result = ev.target?.result as string;
      setPreview(result);
      setModo('preview');
      onCaptura(result.split(',')[1], file.type);
    };
    reader.readAsDataURL(file);
  };

  const reiniciar = () => {
    setPreview(null);
    setModo('idle');
  };

  // ── Modo compacto: solo íconos ─────────────────────────────────────────────
  if (soloBoton) {
    return (
      <div style={{ display: 'inline-flex', flexDirection: 'column', gap: 4, alignItems: 'center' }}>
        {/* Overlay cámara en vivo */}
        {modo === 'camara' && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.88)', zIndex: 1000, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
            <Webcam
              ref={webcamRef}
              screenshotFormat="image/jpeg"
              videoConstraints={{ facingMode: 'environment' }}
              onUserMediaError={() => { setCamaraDisponible(false); setModo('idle'); }}
              style={{ maxWidth: 480, borderRadius: 8 }}
            />
            <div style={{ display: 'flex', gap: 12 }}>
              <button type="button" className="btn-capturar" onClick={capturarFoto}>
                <Camera size={20} /> Tomar Foto
              </button>
              <button type="button" className="btn-cancelar" onClick={() => setModo('idle')}>
                <RotateCcw size={18} /> Cancelar
              </button>
            </div>
          </div>
        )}
        {/* Botones compactos */}
        <div style={{ display: 'flex', gap: 6 }}>
          {camaraDisponible && modo !== 'camara' && (
            <button type="button" title="Capturar con cámara" onClick={() => setModo('camara')}
              style={{ background: '#3B82F6', border: 'none', color: 'white', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
              <Camera size={16} />
            </button>
          )}
          <button type="button" title="Subir imagen" onClick={() => fileInputRef.current?.click()}
            style={{ background: '#6B7280', border: 'none', color: 'white', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <Upload size={16} />
          </button>
          <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={handleFileChange} />
          {preview && (
            <button type="button" title="Reiniciar" onClick={reiniciar}
              style={{ background: '#374151', border: 'none', color: '#9CA3AF', borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}>
              <RotateCcw size={13} />
            </button>
          )}
        </div>
        {preview && (
          <span style={{ color: '#10B981', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}>
            <Check size={11} /> Foto OK
          </span>
        )}
      </div>
    );
  }

  // ── Modo completo ─────────────────────────────────────────────────────────
  return (
    <div className="camara-captura">
      <label className="camara-label">{label}</label>

      {/* Estado idle: botones de selección */}
      {modo === 'idle' && (
        <div className="camara-opciones">
          {camaraDisponible && (
            <button
              type="button"
              className="btn-camara"
              onClick={() => setModo('camara')}
            >
              <Camera size={18} />
              Usar Cámara
            </button>
          )}
          <button
            type="button"
            className="btn-upload"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload size={18} />
            Subir Imagen
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={handleFileChange}
          />
        </div>
      )}

      {/* Vista de cámara en vivo */}
      {modo === 'camara' && (
        <div className="camara-vivo">
          <Webcam
            ref={webcamRef}
            screenshotFormat="image/jpeg"
            videoConstraints={{ facingMode: 'environment' }}
            onUserMediaError={() => {
              setCamaraDisponible(false);
              setModo('idle');
            }}
            className="camara-video"
          />
          <div className="camara-controles">
            <button type="button" className="btn-capturar" onClick={capturarFoto}>
              <Camera size={20} />
              Tomar Foto
            </button>
            <button type="button" className="btn-cancelar" onClick={() => setModo('idle')}>
              <RotateCcw size={18} />
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Preview de la imagen capturada */}
      {modo === 'preview' && preview && (
        <div className="camara-preview">
          <img src={preview} alt="Imagen capturada" className="preview-img" />
          <div className="preview-controles">
            <span className="preview-ok"><Check size={16} /> Imagen lista</span>
            <button type="button" className="btn-reiniciar" onClick={reiniciar}>
              <RotateCcw size={16} />
              Cambiar
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default CamaraCaptura;
