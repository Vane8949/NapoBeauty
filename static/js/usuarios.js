document.addEventListener('DOMContentLoaded', function() {
    const btnUsuario = document.getElementById('btn-agregar-usuario');
    if (btnUsuario) {
        btnUsuario.addEventListener('click', () => abrirModal('modal-usuario'));
    }
});