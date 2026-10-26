/* ==========================================================================
   MÓDULO: LOGIN
   Scripts específicos para la pantalla de inicio de sesión
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function() {
    // Seleccionamos el ícono del ojo y el campo de contraseña
    const togglePassword = document.querySelector('.input-icono-derecha');
    const passwordInput = document.querySelector('input[type="password"]');

    // Verificamos que existan en la página
    if (togglePassword && passwordInput) {
        togglePassword.addEventListener('click', function() {
            // Alternamos el tipo de campo entre 'password' (oculto) y 'text' (visible)
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Alternamos el ícono de FontAwesome (ojo cerrado / ojo abierto)
            this.classList.toggle('fa-eye-slash');
            this.classList.toggle('fa-eye');
        });
    }
});