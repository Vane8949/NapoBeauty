document.addEventListener('DOMContentLoaded', function() {
    const btnDevolucion = document.getElementById('btn-registrar-devolucion');
    if (btnDevolucion) {
        btnDevolucion.addEventListener('click', () => abrirModal('modal-devolucion'));
    }
});