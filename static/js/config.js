// Configuración global del tema de diseño
tailwind.config = {
    theme: {
        extend: {
            colors: {
                napo: { 
                    bg: '#FFF0F5', 
                    light: '#FFD1DC', 
                    primary: '#FF69B4', 
                    text: '#D81B60' 
                }
            }
        }
    }

    
}

// Funciones para controlar el modal de Cerrar Sesión
function abrirModalLogout() {
    const modal = document.getElementById('modal-logout');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function cerrarModalLogout() {
    const modal = document.getElementById('modal-logout');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}
// Abrir y cerrar cualquier modal del panel por su id (ej. abrirModal('modal-inventario'))
function abrirModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function cerrarModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

// Cerrar con la tecla Escape cualquier modal abierto
document.addEventListener('keydown', function(evento) {
    if (evento.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.flex').forEach(function(modal) { cerrarModal(modal.id); });
    }
});
