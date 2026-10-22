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