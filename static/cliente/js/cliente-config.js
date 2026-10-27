// Paleta y tipografías de la tienda (vista cliente) para Tailwind
tailwind.config = {
    theme: {
        extend: {
            colors: {
                rosa: {
                    50: '#FFF6F9',
                    100: '#FDE8EF',
                    200: '#F9D0DE',
                    300: '#F3A8C2',
                    500: '#E9578C',
                    600: '#D63F78',
                    700: '#AF2A62',
                },
                tinta: '#1F1A1C',
            },
            fontFamily: {
                titulo: ['"Playfair Display"', 'Georgia', 'serif'],
                cuerpo: ['Roboto', 'system-ui', 'sans-serif'],
                manuscrita: ['"Dancing Script"', 'cursive'],
            },
        },
    },
};
