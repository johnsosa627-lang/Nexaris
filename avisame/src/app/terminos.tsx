import { Legal } from '../componentes/Legal';
import { ACTUALIZADO, EMAIL_CONTACTO, RESPONSABLE } from '../config';
import { PLANES, formatoPesos } from '../nucleo';

export default function Terminos() {
  return (
    <Legal
      titulo="Términos de uso"
      actualizado={ACTUALIZADO}
      intro={`Avisame es un buscador de vehículos en Uruguay operado por ${RESPONSABLE}. Al usar la app aceptás estos términos.`}
      secciones={[
        {
          titulo: 'Qué es Avisame',
          parrafos: [
            'Avisame junta publicaciones de vehículos de particulares y automotoras para que las encuentres fácil y te avisa cuando aparece lo que buscás.',
            'Avisame no vende vehículos ni participa de la compraventa: el trato es directo entre comprador y vendedor. No garantizamos el estado, la titularidad ni la existencia de los vehículos publicados.',
          ],
        },
        {
          titulo: 'Tu cuenta',
          parrafos: ['Tenés que ser mayor de 18 años. Sos responsable de lo que hagas con tu cuenta y de mantener el acceso a tu email.'],
        },
        {
          titulo: 'Publicar',
          parrafos: [
            'Solo podés publicar vehículos que te pertenecen o que estás autorizado a vender. Los datos y las fotos tienen que ser reales y del vehículo publicado.',
            'Está prohibido publicar contenido falso, engañoso, ofensivo o ilegal, o usar la app para estafas. Podemos pausar o borrar publicaciones y cuentas que no cumplan estos términos.',
            'Al publicar nos das permiso para mostrar tu publicación (fotos y datos) dentro de Avisame.',
          ],
        },
        {
          titulo: 'Fuentes de vehículos',
          parrafos: [
            'Además de lo que se publica en la app, Avisame puede mostrar vehículos obtenidos de fuentes autorizadas, como la API oficial de Mercado Libre o el inventario que un vendedor importa de sus propias cuentas. No usamos scraping ni métodos que violen los términos de otras plataformas.',
          ],
        },
        {
          titulo: 'Seguridad al comprar',
          parrafos: [
            'Nunca pagues señas ni adelantos sin ver el vehículo y verificar los papeles. Revisá el título y pedí un certificado de SUCIVE y del Registro de la Propiedad Mueble. Si algo te parece raro, denunciá la publicación.',
          ],
        },
        {
          titulo: 'Planes para automotoras',
          parrafos: [
            `Planes mensuales en pesos uruguayos: ${PLANES.gratis.nombre} (sin costo), ${PLANES.pro.nombre} (${formatoPesos(PLANES.pro.precioUYU)} por mes) y ${PLANES.destacado.nombre} (${formatoPesos(PLANES.destacado.precioUYU)} por mes).`,
            'El cobro es una suscripción mensual con Mercado Pago. El plan se activa cuando Mercado Pago confirma el pago. Podés cancelar la renovación cuando quieras desde el panel: el plan sigue hasta el final del período pagado y no se hacen devoluciones proporcionales, salvo que la ley lo exija.',
            'Los contactos de clientes solo se muestran si el cliente lo autorizó. La automotora se compromete a usarlos únicamente para ofrecer vehículos relacionados con su búsqueda y a no compartirlos con terceros.',
          ],
        },
        {
          titulo: 'Responsabilidad',
          parrafos: [
            'Hacemos lo posible para que la app funcione bien, pero puede tener interrupciones o errores. Las distancias son en línea recta y aproximadas. En la medida que la ley lo permita, no somos responsables por las operaciones entre usuarios.',
          ],
        },
        {
          titulo: 'Cambios y contacto',
          parrafos: [
            `Podemos actualizar estos términos; te avisamos en la app. Consultas: ${EMAIL_CONTACTO}. Estos términos se rigen por las leyes de la República Oriental del Uruguay.`,
          ],
        },
      ]}
    />
  );
}
