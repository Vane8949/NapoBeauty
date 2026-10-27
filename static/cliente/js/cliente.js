/* ==========================================================================
   VISTA CLIENTE - Interacciones
   Por ahora todo es visual: favoritos y carrito solo cambian en pantalla.
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {
    const escritorio = window.matchMedia('(min-width: 1024px)');

    // ---------- Menú lateral (hamburguesa) ----------
    const btnHamburguesa = document.getElementById('btn-hamburguesa');
    const barraLateral = document.getElementById('barra-lateral');
    const fondoMenu = document.getElementById('fondo-menu');

    function cerrarLateralMovil() {
        barraLateral.classList.remove('abierta');
        fondoMenu.classList.add('hidden');
        btnHamburguesa.setAttribute('aria-expanded', 'false');
    }

    if (btnHamburguesa && barraLateral) {
        btnHamburguesa.addEventListener('click', function () {
            let abierto;
            if (escritorio.matches) {
                abierto = !barraLateral.classList.toggle('colapsada');
            } else {
                abierto = barraLateral.classList.toggle('abierta');
                fondoMenu.classList.toggle('hidden', !abierto);
            }
            btnHamburguesa.setAttribute('aria-expanded', String(abierto));
            if (!abierto) cerrarMegaMenu();
        });
        fondoMenu.addEventListener('click', function () {
            cerrarLateralMovil();
            cerrarMegaMenu();
        });
        escritorio.addEventListener('change', cerrarLateralMovil);
    }

    // ---------- Menú de categorías ----------
    const btnCategorias = document.getElementById('btn-categorias');
    const megaMenu = document.getElementById('mega-menu');
    const contenedor = document.getElementById('contenedor-cliente');

    function cerrarMegaMenu() {
        if (!megaMenu) return;
        megaMenu.classList.add('hidden');
        btnCategorias.classList.remove('activo');
        btnCategorias.setAttribute('aria-expanded', 'false');
    }

    function abrirMegaMenu() {
        if (escritorio.matches) {
            // Lo alinea justo debajo del botón "Todas las categorías"
            const arriba = btnCategorias.getBoundingClientRect().bottom - contenedor.getBoundingClientRect().top + 6;
            megaMenu.style.top = arriba + 'px';
        } else {
            megaMenu.style.top = '';
        }
        megaMenu.classList.remove('hidden');
        btnCategorias.classList.add('activo');
        btnCategorias.setAttribute('aria-expanded', 'true');
    }

    if (btnCategorias && megaMenu) {
        btnCategorias.addEventListener('click', function (e) {
            e.stopPropagation();
            megaMenu.classList.contains('hidden') ? abrirMegaMenu() : cerrarMegaMenu();
        });
        megaMenu.addEventListener('click', function (e) { e.stopPropagation(); });
    }

    // ---------- Menú de usuario ----------
    const btnUsuario = document.getElementById('btn-usuario');
    const menuUsuario = document.getElementById('menu-usuario');

    function cerrarMenuUsuario() {
        if (!menuUsuario) return;
        menuUsuario.classList.add('hidden');
        btnUsuario.setAttribute('aria-expanded', 'false');
    }

    if (btnUsuario && menuUsuario) {
        btnUsuario.addEventListener('click', function (e) {
            e.stopPropagation();
            const abrir = menuUsuario.classList.contains('hidden');
            menuUsuario.classList.toggle('hidden', !abrir);
            btnUsuario.setAttribute('aria-expanded', String(abrir));
        });
        menuUsuario.addEventListener('click', function (e) { e.stopPropagation(); });
    }

    // Cerrar menús al hacer clic fuera o con la tecla Escape
    document.addEventListener('click', function () {
        cerrarMegaMenu();
        cerrarMenuUsuario();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            cerrarMegaMenu();
            cerrarMenuUsuario();
            if (!escritorio.matches) cerrarLateralMovil();
        }
    });

    // ---------- Aviso flotante ----------
    const aviso = document.getElementById('aviso');
    let temporizadorAviso;
    function mostrarAviso(texto) {
        if (!aviso) return;
        aviso.textContent = texto;
        aviso.classList.add('visible');
        clearTimeout(temporizadorAviso);
        temporizadorAviso = setTimeout(() => aviso.classList.remove('visible'), 2200);
    }

    function actualizarContador(id, cambio) {
        const contador = document.getElementById(id);
        if (!contador) return;
        const valor = Math.max(0, (parseInt(contador.textContent, 10) || 0) + cambio);
        contador.textContent = valor;
        contador.classList.remove('salta');
        void contador.offsetWidth; // reinicia la animación
        contador.classList.add('salta');
    }

    // ---------- Favoritos ----------
    document.querySelectorAll('.btn-favorito').forEach(function (boton) {
        boton.addEventListener('click', function () {
            const activo = boton.getAttribute('aria-pressed') !== 'true';
            boton.setAttribute('aria-pressed', String(activo));
            const icono = boton.querySelector('i');
            icono.classList.toggle('fa-solid', activo);
            icono.classList.toggle('fa-regular', !activo);
            actualizarContador('contador-favoritos', activo ? 1 : -1);
            mostrarAviso(activo ? 'Agregado a favoritos' : 'Quitado de favoritos');
        });
    });

    // ---------- Agregar al carrito ----------
    document.querySelectorAll('.btn-carrito').forEach(function (boton) {
        boton.addEventListener('click', function () {
            if (boton.classList.contains('agregado')) return;
            const texto = boton.querySelector('span');
            const original = texto.textContent;
            boton.classList.add('agregado');
            texto.textContent = '¡Agregado!';
            actualizarContador('contador-carrito', 1);
            mostrarAviso('Producto agregado al carrito');
            setTimeout(function () {
                boton.classList.remove('agregado');
                texto.textContent = original;
            }, 1500);
        });
    });
});
