/* ==========================================================================
   VENTANA EMERGENTE DE AGREGAR / EDITAR
   - Cualquier enlace con el atributo data-modal abre su formulario en la ventana.
   - El formulario se envía sin salir de la página; si hay errores, se muestran
     en la misma ventana; si se guardó, la página se recarga con el aviso.
   ========================================================================== */
(function () {
    const fondo = document.getElementById('modal-dinamico');
    const caja = document.getElementById('modal-dinamico-contenido');
    if (!fondo || !caja) return;

    const CARGANDO = '<div class="bg-white rounded-2xl shadow-2xl px-10 py-8 text-gray-500 text-sm">' +
        '<i class="fa-solid fa-spinner fa-spin mr-2 text-pink-500"></i>Cargando...</div>';

    function abrir() {
        fondo.classList.remove('hidden');
        fondo.classList.add('flex');
        document.body.classList.add('overflow-hidden');
    }

    function cerrar() {
        fondo.classList.add('hidden');
        fondo.classList.remove('flex');
        document.body.classList.remove('overflow-hidden');
        caja.innerHTML = '';
    }

    function mostrarError(texto) {
        caja.innerHTML = '<div class="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full text-center">' +
            '<i class="fa-solid fa-circle-exclamation text-3xl text-red-500 mb-3"></i>' +
            '<p class="text-gray-700 mb-6"></p>' +
            '<button type="button" data-cerrar-modal class="px-6 py-2.5 rounded-xl bg-pink-500 text-white font-bold text-sm">Entendido</button></div>';
        caja.querySelector('p').textContent = texto;
    }

    async function mostrarRespuesta(respuesta) {
        const tipo = respuesta.headers.get('Content-Type') || '';
        if (tipo.includes('application/json')) {
            const datos = await respuesta.json();
            if (datos.ok) {
                // ir: abrir otra página (ej. el recibo de la venta); si no, recargar la actual
                if (datos.ir && datos.url) window.location.href = datos.url;
                else window.location.reload();
            } else {
                mostrarError(datos.error || 'No se pudo completar la acción.');
            }
            return;
        }
        if (!respuesta.ok) {
            mostrarError('Ocurrió un error en el servidor (' + respuesta.status + '). Revisa la consola de Django.');
            return;
        }
        caja.innerHTML = await respuesta.text();
        activar(caja);
        const primerCampo = caja.querySelector('input:not([type=hidden]):not(.sr-only), select, textarea');
        if (primerCampo) primerCampo.focus({ preventScroll: true });
    }

    async function cargar(url) {
        caja.innerHTML = CARGANDO;
        abrir();
        try {
            const respuesta = await fetch(url, { headers: { 'X-Modal': '1' } });
            await mostrarRespuesta(respuesta);
        } catch (error) {
            mostrarError('No se pudo conectar con el servidor.');
        }
    }

    // ---------- Comportamientos dentro del formulario ----------
    function activar(contenedor) {
        activarImagenes(contenedor);
        activarLineasVenta(contenedor);
        activarTonos(contenedor);
        activarMostrarSi(contenedor);

        // Selects que vuelven a cargar el formulario al cambiar (ej. la venta de una devolución)
        contenedor.querySelectorAll('[data-recargar]').forEach(function (select) {
            select.addEventListener('change', function () {
                const url = new URL(select.dataset.recargar, window.location.origin);
                if (select.value) url.searchParams.set(select.name, select.value);
                cargar(url.toString());
            });
        });
    }

    // Campos que solo aparecen con cierta opción: data-mostrar-si="tipo_cliente=nuevo"
    function activarMostrarSi(contenedor) {
        const campos = contenedor.querySelectorAll('[data-mostrar-si]');
        if (!campos.length) return;
        const form = campos[0].closest('form');

        function valorDe(nombre) {
            const marcado = form.querySelector('[name="' + nombre + '"]:checked');
            if (marcado) return marcado.value;
            const campo = form.querySelector('[name="' + nombre + '"]:not([type=radio]):not([type=checkbox])');
            return campo ? campo.value : '';
        }

        function actualizar() {
            campos.forEach(function (bloque) {
                const partes = bloque.dataset.mostrarSi.split('=');
                bloque.classList.toggle('hidden', valorDe(partes[0]) !== partes[1]);
            });
        }

        const nombres = new Set();
        campos.forEach(function (bloque) { nombres.add(bloque.dataset.mostrarSi.split('=')[0]); });
        nombres.forEach(function (nombre) {
            form.querySelectorAll('[name="' + nombre + '"]').forEach(function (campo) {
                campo.addEventListener('change', function () {
                    actualizar();
                    const visible = form.querySelector('[data-mostrar-si]:not(.hidden) input, [data-mostrar-si]:not(.hidden) select');
                    if (visible && campo.type === 'radio') visible.focus({ preventScroll: true });
                });
            });
        });
        actualizar();
    }

    function activarImagenes(contenedor) {
        contenedor.querySelectorAll('[data-zona-imagen]').forEach(function (zona) {
            const input = zona.querySelector('input[type=file]');
            const vista = zona.querySelector('[data-vista-previa]');
            const nombre = zona.querySelector('[data-nombre-archivo]');
            if (!input) return;

            function mostrarArchivo() {
                const archivo = input.files && input.files[0];
                if (!archivo) return;
                if (archivo.size > 2 * 1024 * 1024) {
                    nombre.textContent = 'La imagen pesa más de 2 MB. Elige otra.';
                    input.value = '';
                    return;
                }
                nombre.textContent = archivo.name;
                vista.src = URL.createObjectURL(archivo);
                vista.classList.remove('hidden');
            }

            input.addEventListener('change', mostrarArchivo);
            ['dragenter', 'dragover'].forEach(function (evento) {
                zona.addEventListener(evento, function (e) { e.preventDefault(); zona.classList.add('border-pink-500'); });
            });
            ['dragleave', 'drop'].forEach(function (evento) {
                zona.addEventListener(evento, function () { zona.classList.remove('border-pink-500'); });
            });
            zona.addEventListener('drop', function (e) {
                e.preventDefault();
                if (e.dataTransfer.files.length) {
                    input.files = e.dataTransfer.files;
                    mostrarArchivo();
                }
            });
        });
    }

    function formatoCordobas(valor) {
        return 'C$ ' + valor.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // Tonos de un producto: "Agregar tono" copia la fila vacía de la plantilla
    function activarTonos(contenedor) {
        const bloque = contenedor.querySelector('[data-tonos]');
        if (!bloque) return;
        const lista = bloque.querySelector('[data-lista-tonos]');
        const plantilla = bloque.querySelector('template[data-plantilla-tono]');
        const totalForms = bloque.querySelector('#id_' + bloque.dataset.prefijo + '-TOTAL_FORMS');
        // Vista previa de la foto de cada tono (también en las filas que se agregan después)
        lista.addEventListener('change', function (e) {
            if (e.target.type !== 'file' || !e.target.files.length) return;
            const fila = e.target.closest('[data-tono]');
            const archivo = e.target.files[0];
            if (archivo.size > 2 * 1024 * 1024) { e.target.value = ''; alertaFoto(fila); return; }
            const foto = fila.querySelector('[data-foto-tono]');
            foto.src = URL.createObjectURL(archivo);
            foto.classList.remove('hidden');
            fila.querySelector('[data-icono-foto]').classList.add('hidden');
        });
        function alertaFoto(fila) {
            const nombre = fila.querySelector('input[name$="-nombre"]');
            if (nombre) { nombre.setCustomValidity('La foto pesa más de 2 MB.'); nombre.reportValidity(); nombre.setCustomValidity(''); }
        }
        bloque.querySelector('[data-agregar-tono]').addEventListener('click', function () {
            const indice = parseInt(totalForms.value, 10);
            lista.insertAdjacentHTML('beforeend', plantilla.innerHTML.replace(/__prefix__/g, indice));
            totalForms.value = indice + 1;
            const nombre = lista.lastElementChild.querySelector('input[name$="-nombre"]');
            if (nombre) nombre.focus();
        });
    }

    function activarLineasVenta(contenedor) {
        const bloque = contenedor.querySelector('[data-lineas]');
        if (!bloque) return;
        const prefijo = bloque.dataset.prefijo;
        const lista = bloque.querySelector('[data-lista-lineas]');
        const plantilla = bloque.querySelector('template[data-plantilla-linea]');
        const totalForms = bloque.querySelector('#id_' + prefijo + '-TOTAL_FORMS');
        const form = bloque.closest('form');

        function escribir(selector, texto) {
            const elemento = bloque.querySelector(selector);
            if (elemento) elemento.textContent = texto;
        }

        function recalcular() {
            let subtotal = 0;
            lista.querySelectorAll('[data-linea]').forEach(function (linea) {
                if (linea.classList.contains('hidden')) return;
                const select = linea.querySelector('select');
                const cantidad = parseInt(linea.querySelector('input[type=number]').value, 10) || 0;
                const opcion = select.options[select.selectedIndex];
                const precio = opcion ? parseFloat(opcion.dataset.precio || '0') : 0;
                const stock = opcion ? parseInt(opcion.dataset.stock || '0', 10) : 0;
                const importe = precio * cantidad;
                subtotal += importe;
                linea.querySelector('[data-importe]').textContent = formatoCordobas(importe);
                const aviso = linea.querySelector('[data-aviso-stock]');
                if (opcion && opcion.value && cantidad > stock) {
                    aviso.textContent = 'Solo hay ' + stock + ' en stock';
                    aviso.classList.remove('hidden');
                } else {
                    aviso.classList.add('hidden');
                }
            });
            const descuentoInput = form.querySelector('[name=descuento]');
            const descuento = descuentoInput ? (parseFloat(descuentoInput.value) || 0) : 0;
            escribir('[data-subtotal]', formatoCordobas(subtotal));
            escribir('[data-descuento]', '− ' + formatoCordobas(descuento));
            escribir('[data-total]', formatoCordobas(Math.max(subtotal - descuento, 0)));
        }

        function prepararLinea(linea) {
            linea.querySelectorAll('select, input').forEach(function (campo) {
                campo.addEventListener('input', recalcular);
                campo.addEventListener('change', recalcular);
            });
            const quitar = linea.querySelector('[data-quitar-linea]');
            if (quitar) {
                quitar.addEventListener('click', function () {
                    const borrar = linea.querySelector('input[name$="-DELETE"]');
                    if (borrar) borrar.checked = true;
                    linea.classList.add('hidden');
                    recalcular();
                });
            }
        }

        lista.querySelectorAll('[data-linea]').forEach(prepararLinea);
        bloque.querySelector('[data-agregar-linea]').addEventListener('click', function () {
            const indice = parseInt(totalForms.value, 10);
            const html = plantilla.innerHTML.replace(/__prefix__/g, indice);
            lista.insertAdjacentHTML('beforeend', html);
            totalForms.value = indice + 1;
            prepararLinea(lista.lastElementChild);
            recalcular();
        });
        const descuentoInput = form.querySelector('[name=descuento]');
        if (descuentoInput) descuentoInput.addEventListener('input', recalcular);
        recalcular();
    }

    // ---------- Eventos globales ----------
    document.addEventListener('click', function (e) {
        const enlace = e.target.closest('[data-modal]');
        if (enlace) {
            e.preventDefault();
            cargar(enlace.getAttribute('href') || enlace.dataset.url);
            return;
        }
        if (e.target.closest('[data-cerrar-modal]')) {
            e.preventDefault();
            cerrar();
        }
    });

    fondo.addEventListener('mousedown', function (e) {
        if (e.target === fondo || e.target === caja) cerrar();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !fondo.classList.contains('hidden')) cerrar();
    });

    document.addEventListener('submit', async function (e) {
        const form = e.target;
        if (!caja.contains(form)) return;
        e.preventDefault();
        const boton = form.querySelector('[type=submit]');
        if (boton) {
            boton.disabled = true;
            boton.textContent = boton.dataset.textoGuardando || 'Guardando...';
        }
        try {
            const respuesta = await fetch(form.action, {
                method: 'POST', body: new FormData(form), headers: { 'X-Modal': '1' },
            });
            await mostrarRespuesta(respuesta);
        } catch (error) {
            mostrarError('No se pudo conectar con el servidor.');
        }
    });
})();
