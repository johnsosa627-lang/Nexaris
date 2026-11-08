/** Sitios de ejemplo para las pruebas del analizador (inventados). */

export const BAD_SITE = `<!doctype html>
<html>
<head>
  <title>Inicio</title>
  <script src="http://cdn.inseguro.example/lib.js"></script>
  <script>!function(f,b,e,v,n,t,s){}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js'); fbq('init', '123');</script>
</head>
<body>
  <h1>Bienvenidos</h1><h1>Autos usados</h1>
  <img src="a.jpg"><img src="b.jpg"><img src="c.jpg"><img src="d.jpg"><img src="e.jpg" alt="auto">
  <p>Llamanos o escribinos a ventas@automotora-mala.example</p>
  <footer>© 2019 Automotora Mala</footer>
</body>
</html>`;

export const GOOD_SITE = `<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Inmobiliaria Buena | Casas y apartamentos en Montevideo</title>
  <meta name="description" content="Compra, venta y alquiler de propiedades en Montevideo. Tasaciones sin costo y atención por WhatsApp.">
  <meta property="og:image" content="https://inmo-buena.example/og.jpg">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC1234567"></script>
  <script>window.dataLayer=[];function gtag(){dataLayer.push(arguments)}gtag('config','G-ABC1234567');gtag('config','AW-123456789');</script>
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"RealEstateAgent","name":"Inmobiliaria Buena"}</script>
</head>
<body>
  <h1>Encontrá tu próximo hogar</h1>
  <a href="https://wa.me/59899123456?text=Hola">WhatsApp</a>
  <a href="tel:+598 2 123 4567">Llamar</a>
  <a href="mailto:info@inmo-buena.example">info@inmo-buena.example</a>
  <a href="/contacto">Contacto</a>
  <a href="https://www.instagram.com/inmobuena">Instagram</a>
  <a href="https://www.facebook.com/inmobuena">Facebook</a>
  <a href="https://www.facebook.com/sharer/sharer.php?u=x">Compartir</a>
  <form><input name="nombre"><input name="email"><textarea name="msg"></textarea></form>
  <img src="casa.jpg" alt="Casa en Pocitos">
  <p>${"Propiedades seleccionadas en los mejores barrios. ".repeat(60)}</p>
  <a href="/privacidad">Política de privacidad</a>
  <footer>© 2026 Inmobiliaria Buena</footer>
</body>
</html>`;
