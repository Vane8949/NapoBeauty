document.addEventListener('DOMContentLoaded', function() {
    const btnProveedor = document.getElementById('btn-registrar-proveedor');
    if (btnProveedor) {
        btnProveedor.addEventListener('click', () => abrirModal('modal-proveedor'));
    }
});