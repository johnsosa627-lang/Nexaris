import { Legal } from '../componentes/Legal';
import { ACTUALIZADO, DOMICILIO, EMAIL_CONTACTO, RESPONSABLE } from '../config';

export default function Privacidad() {
  return (
    <Legal
      titulo="Política de privacidad"
      actualizado={ACTUALIZADO}
      intro={`Esta política explica qué datos personales trata Avisame, para qué y cuáles son tus derechos, de acuerdo con la Ley N.º 18.331 de Protección de Datos Personales y Acción de Habeas Data de Uruguay y su Decreto reglamentario N.º 414/009.`}
      secciones={[
        {
          titulo: 'Responsable',
          parrafos: [`El responsable de la base de datos es ${RESPONSABLE}, con domicilio en ${DOMICILIO}. Contacto: ${EMAIL_CONTACTO}.`],
        },
        {
          titulo: 'Qué datos tratamos',
          parrafos: [
            'Cuenta: tu email (para ingresar con un código, sin contraseña).',
            'Publicaciones: los datos del vehículo, las fotos que subís, la ubicación del vehículo (departamento, ciudad y, si la ponés, la dirección) y el nombre y WhatsApp de contacto que elegís mostrar.',
            'Búsquedas guardadas: lo que buscás, tu nombre, tu WhatsApp, tu zona y si autorizás que te contacten automotoras.',
            'Automotoras: nombre comercial, dirección, teléfono, plan contratado e historial de pagos. Los datos de la tarjeta los maneja Mercado Pago; Avisame no los recibe.',
            'Notificaciones: un identificador del celular para mandarte avisos.',
            'Ubicación: si lo permitís, la ubicación aproximada del celular, solo para calcular distancias en tu equipo. No la guardamos en el servidor; para tus búsquedas guardadas guardamos la ciudad o zona.',
          ],
        },
        {
          titulo: 'Para qué los usamos',
          parrafos: [
            'Para mostrar vehículos y ordenarlos por cercanía, publicar tus vehículos, avisarte cuando aparece lo que buscás, permitir que las automotoras te contacten solo si lo autorizaste, gestionar los planes de las automotoras y prevenir fraudes y abusos.',
            'No vendemos tus datos ni mostramos publicidad.',
          ],
        },
        {
          titulo: 'Base legal y consentimiento',
          parrafos: [
            'Tratamos tus datos con tu consentimiento, que das al crear la cuenta, publicar o guardar una búsqueda. El contacto con automotoras requiere un consentimiento aparte, con una casilla que podés no marcar.',
          ],
        },
        {
          titulo: 'Con quién se comparten',
          parrafos: [
            'Los datos de contacto de una publicación son públicos: los ve cualquiera que mire el vehículo.',
            'Tu nombre y WhatsApp de una búsqueda guardada solo se comparten con automotoras que tengan un vehículo que coincide, que tengan un plan pago al día, y solo si marcaste la casilla de autorización.',
            'Usamos proveedores que procesan datos por cuenta nuestra: Supabase (base de datos y archivos), Expo y Google Firebase (envío de notificaciones) y Mercado Pago (cobros). Algunos de estos servicios pueden almacenar datos fuera de Uruguay; en ese caso se exigen garantías adecuadas según el artículo 23 de la Ley 18.331.',
            'Al tocar "Ver en el mapa" se abre Google Maps, y al tocar WhatsApp se abre esa aplicación, con sus propias políticas.',
          ],
        },
        {
          titulo: 'Cuánto tiempo los guardamos',
          parrafos: [
            'Mientras tengas la cuenta. Si borrás una publicación o una búsqueda, se borra. Los registros de pagos pueden conservarse el tiempo que exijan las normas contables y tributarias.',
          ],
        },
        {
          titulo: 'Tus derechos',
          parrafos: [
            'Tenés derecho de acceso, rectificación, actualización, inclusión y supresión de tus datos (artículos 14 y 15 de la Ley 18.331). Podés editar o borrar tus publicaciones y búsquedas desde la app, y borrar tu cuenta entera desde Cuenta → Borrar mi cuenta: se eliminan tus datos, fotos y se cancela cualquier suscripción.',
            `También podés escribirnos a ${EMAIL_CONTACTO}. Respondemos dentro de los plazos legales (5 días hábiles para el acceso).`,
            'Si no quedás conforme, podés presentar una denuncia ante la Unidad Reguladora y de Control de Datos Personales (URCDP), www.gub.uy/urcdp.',
          ],
        },
        {
          titulo: 'Permisos del celular',
          parrafos: [
            'Cámara y fotos: solo para que elijas o saques las fotos de tu vehículo.',
            'Ubicación aproximada: solo si tocás "Usar la ubicación del celular", para ordenar por cercanía.',
            'Notificaciones: para avisarte cuando aparece lo que buscás o, si sos automotora, cuando aparece un cliente.',
            'Podés negar o retirar cualquiera de estos permisos desde los ajustes del celular; la app sigue funcionando.',
          ],
        },
        {
          titulo: 'Seguridad',
          parrafos: [
            'Usamos conexiones cifradas y reglas de acceso en la base de datos para que cada persona vea solo lo que le corresponde. Ningún sistema es infalible: si detectamos un incidente que te afecte, te avisamos.',
          ],
        },
        {
          titulo: 'Menores de edad',
          parrafos: ['Avisame está pensada para mayores de 18 años. No recolectamos a sabiendas datos de menores.'],
        },
        {
          titulo: 'Cambios',
          parrafos: ['Si cambiamos esta política te avisamos en la app. La fecha de arriba indica la última actualización.'],
        },
      ]}
    />
  );
}
