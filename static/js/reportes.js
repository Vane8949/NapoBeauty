/* Reportes: gráficas con los datos de la base (json_script), reloj y fechas personalizadas. */
document.addEventListener('DOMContentLoaded', function () {
    function leer(id) {
        const nodo = document.getElementById(id);
        return nodo ? JSON.parse(nodo.textContent) : null;
    }
    function cordobas(valor) {
        return 'C$ ' + Number(valor).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // "Personalizado" muestra Desde / Hasta
    const rango = document.querySelector('[data-rango]');
    const fechas = document.querySelector('[data-fechas]');
    if (rango && fechas) {
        rango.addEventListener('change', function () { fechas.classList.toggle('hidden', rango.value !== 'personalizado'); });
    }

    const reloj = document.querySelector('[data-reloj]');
    if (reloj) {
        const ponerHora = function () {
            reloj.textContent = new Date().toLocaleTimeString('es-NI', { hour: '2-digit', minute: '2-digit', hour12: true });
        };
        ponerHora();
        setInterval(ponerHora, 30000);
    }

    if (typeof Chart === 'undefined') return;
    const tooltip = { backgroundColor: '#831843', padding: 10, cornerRadius: 8 };

    // 1. Ingresos vs. costos de los últimos 6 meses
    const meses = leer('datos-meses');
    const lienzoMeses = document.getElementById('graficoIngresosCostos');
    if (meses && lienzoMeses) {
        new Chart(lienzoMeses.getContext('2d'), {
            type: 'bar',
            data: {
                labels: meses.etiquetas,
                datasets: [
                    { label: 'Ingresos', data: meses.ingresos, backgroundColor: '#EC4899', borderRadius: 6, maxBarThickness: 34 },
                    { label: 'Costo de lo vendido', data: meses.costos, backgroundColor: '#C4B5FD', borderRadius: 6, maxBarThickness: 34 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, color: '#4b5563' } },
                    tooltip: Object.assign({}, tooltip, {
                        callbacks: { label: function (c) { return ' ' + c.dataset.label + ': ' + cordobas(c.parsed.y); } },
                    }),
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#f3f4f6' }, border: { display: false },
                         ticks: { callback: function (v) { return 'C$ ' + Number(v).toLocaleString('en-US'); } } },
                    x: { grid: { display: false }, border: { display: false } },
                },
            },
        });
    }

    // 2. Ventas por categoría del periodo
    const categorias = leer('datos-categorias');
    const lienzoCategorias = document.getElementById('graficoCategorias');
    if (categorias && lienzoCategorias && categorias.ingresos.length) {
        const total = categorias.ingresos.reduce(function (a, b) { return a + b; }, 0);
        new Chart(lienzoCategorias.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: categorias.etiquetas,
                datasets: [{
                    data: categorias.ingresos,
                    backgroundColor: ['#D81B60', '#FF69B4', '#C084FC', '#F9A8D4', '#FBCFE8', '#A78BFA', '#E5E7EB'],
                    borderWidth: 2, borderColor: '#ffffff', hoverOffset: 4,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, padding: 10, color: '#4b5563' } },
                    tooltip: Object.assign({}, tooltip, {
                        callbacks: {
                            label: function (c) {
                                const pct = total ? Math.round(c.parsed * 1000 / total) / 10 : 0;
                                return ' ' + c.label + ': ' + cordobas(c.parsed) + ' (' + pct + '%)';
                            },
                        },
                    }),
                },
            },
        });
    }
});
