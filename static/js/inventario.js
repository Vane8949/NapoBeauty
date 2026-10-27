document.addEventListener('DOMContentLoaded', function() {
    const btnAjustar = document.getElementById('btn-ajustar-stock');
    if (btnAjustar) {
        btnAjustar.addEventListener('click', () => abrirModal('modal-inventario'));
    }

    // Al elegir un producto en el modal, abre su pantalla de ajuste
    const form = document.getElementById('form-elegir-producto');
    if (form) {
        form.addEventListener('submit', function(evento) {
            evento.preventDefault();
            const id = document.getElementById('producto-ajuste').value;
            if (id) {
                window.location.href = form.dataset.url.replace('/0/', '/' + id + '/');
            }
        });
    }
});
