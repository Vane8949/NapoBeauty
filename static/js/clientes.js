document.addEventListener('DOMContentLoaded', function() {
    const btnCliente = document.getElementById('btn-registrar-cliente');
    if (btnCliente) {
        btnCliente.addEventListener('click', () => abrirModal('modal-cliente'));
    }
});