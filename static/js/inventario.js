document.addEventListener('DOMContentLoaded', function() {
    const btnAjustar = document.getElementById('btn-ajustar-stock');
    if (btnAjustar) {
        btnAjustar.addEventListener('click', () => abrirModal('modal-inventario'));
    }
});