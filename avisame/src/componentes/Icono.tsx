// Íconos propios en SVG (trazo de 2 px), sin depender de fuentes de íconos.
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { colores } from '../tema';

export type NombreIcono =
  | 'buscar' | 'campana' | 'mas' | 'persona' | 'x' | 'ubicacion' | 'gps' | 'whatsapp' | 'telefono' | 'mapa'
  | 'camara' | 'galeria' | 'bandera' | 'check' | 'flecha' | 'atras' | 'estrella' | 'auto' | 'editar'
  | 'pausa' | 'play' | 'basura' | 'tienda' | 'candado' | 'info' | 'salir' | 'abajo';

export function Icono({ nombre, tam = 22, color = colores.tinta, relleno = false }: { nombre: NombreIcono; tam?: number; color?: string; relleno?: boolean }) {
  const p = { stroke: color, strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, fill: 'none' };
  const f = relleno ? color : 'none';
  return (
    <Svg width={tam} height={tam} viewBox="0 0 24 24">
      {(() => {
        switch (nombre) {
          case 'buscar': return <><Circle cx={11} cy={11} r={6.5} {...p} /><Path d="M16 16l4.5 4.5" {...p} /></>;
          case 'campana': return <><Path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z" {...p} fill={f} /><Path d="M10 20.5a2 2 0 0 0 4 0" {...p} /></>;
          case 'mas': return <><Circle cx={12} cy={12} r={9} {...p} fill={f} /><Path d="M12 8v8M8 12h8" {...p} stroke={relleno ? colores.blanco : color} /></>;
          case 'persona': return <><Circle cx={12} cy={8} r={4} {...p} fill={f} /><Path d="M4 20.5c1.5-4 4.5-5.5 8-5.5s6.5 1.5 8 5.5" {...p} fill={f} /></>;
          case 'x': return <Path d="M6 6l12 12M18 6L6 18" {...p} />;
          case 'ubicacion': return <><Path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 1 1 13 0c0 4.8-6.5 11-6.5 11z" {...p} fill={f} /><Circle cx={12} cy={10} r={2.3} {...p} /></>;
          case 'gps': return <><Circle cx={12} cy={12} r={6} {...p} /><Circle cx={12} cy={12} r={2} {...p} fill={color} /><Path d="M12 2v3M12 19v3M2 12h3M19 12h3" {...p} /></>;
          case 'whatsapp': return <><Path d="M4 20l1.2-4A8 8 0 1 1 8 19z" {...p} /><Path d="M9 9.5c.3 2.4 2.2 4.5 4.8 5.2l1.3-1.2-1.6-1-1 .8c-.9-.4-1.8-1.3-2.2-2.2l.8-1-1-1.6z" fill={color} /></>;
          case 'telefono': return <Path d="M5 4h3.5l1.5 4-2 1.5a11 11 0 0 0 6.5 6.5l1.5-2 4 1.5V19a1.5 1.5 0 0 1-1.6 1.5A16 16 0 0 1 3.5 5.6 1.5 1.5 0 0 1 5 4z" {...p} />;
          case 'mapa': return <><Path d="M3 6.5l6-2.5 6 2.5 6-2.5v13.5L15 20l-6-2.5L3 20z" {...p} /><Path d="M9 4v13.5M15 6.5V20" {...p} /></>;
          case 'camara': return <><Path d="M3.5 8h4l1.5-2.5h6L16.5 8h4v11.5h-17z" {...p} /><Circle cx={12} cy={13.5} r={3.5} {...p} /></>;
          case 'galeria': return <><Rect x={3.5} y={4.5} width={17} height={15} rx={2} {...p} /><Circle cx={9} cy={10} r={1.8} {...p} /><Path d="M4 17l5-4.5 4 3.5 3-2.5 4 3.5" {...p} /></>;
          case 'bandera': return <Path d="M5 21V4.5h11l-2 3.5 2 3.5H5" {...p} />;
          case 'check': return <Path d="M5 12.5l4.5 4.5L19 7.5" {...p} />;
          case 'flecha': return <Path d="M9 5l7 7-7 7" {...p} />;
          case 'atras': return <Path d="M15 5l-7 7 7 7" {...p} />;
          case 'abajo': return <Path d="M6 9l6 6 6-6" {...p} />;
          case 'estrella': return <Path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z" {...p} fill={f} />;
          case 'auto': return <><Path d="M3.5 16.5v-4l2-5h13l2 5v4z" {...p} /><Circle cx={7.5} cy={16.5} r={1.8} {...p} /><Circle cx={16.5} cy={16.5} r={1.8} {...p} /></>;
          case 'editar': return <Path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4" {...p} />;
          case 'pausa': return <Path d="M9 5v14M15 5v14" {...p} />;
          case 'play': return <Path d="M7 4.5v15l12-7.5z" {...p} />;
          case 'basura': return <Path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13M10 11v5M14 11v5" {...p} />;
          case 'tienda': return <><Path d="M4 9.5L5.5 4h13L20 9.5a2.7 2.7 0 0 1-5.3 0 2.7 2.7 0 0 1-5.4 0 2.7 2.7 0 0 1-5.3 0z" {...p} /><Path d="M5 11.5V20h14v-8.5M10 20v-5h4v5" {...p} /></>;
          case 'candado': return <><Rect x={5} y={10.5} width={14} height={10} rx={2} {...p} /><Path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" {...p} /></>;
          case 'info': return <><Circle cx={12} cy={12} r={9} {...p} /><Path d="M12 11v6M12 7.5v.5" {...p} /></>;
          case 'salir': return <Path d="M14 4.5h5v15h-5M10 8l-4 4 4 4M6 12h10" {...p} />;
        }
      })()}
    </Svg>
  );
}
