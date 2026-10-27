/* Gráficas y reloj del Dashboard. Los datos vienen de la base en
   <script id="datos-ventas-dias"> y <script id="datos-top-productos"> (json_script de Django). */
document.addEventListener('DOMContentLoaded', function () {
    function leer(id) {
        const nodo = document.getElementById(id);
        return nodo ? JSON.parse(nodo.textContent) : null;
    }
    function cordobas(valor) {
        return 'C$ ' + Number(valor).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // Reloj: se actualiza cada 30 segundos
    const reloj = document.querySelector('[data-reloj]');
    if (reloj) {
        const ponerHora = function () {
            reloj.textContent = new Date().toLocaleTimeString('es-NI', { hour: '2-digit', minute: '2-digit', hour12: true });
        };
        ponerHora();
        setInterval(ponerHora, 30000);
    }

    if (typeof Chart === 'undefined') return;

    // 1. Ventas de los últimos 7 días (C$ o número de ventas)
    const dias = leer('datos-ventas-dias');
    const canvasLine = document.getElementById('lineChart');
    if (dias && canvasLine) {
        const ctx = canvasLine.getContext('2d');
        const gradiente = ctx.createLinearGradient(0, 0, 0, 400);
        gradiente.addColorStop(0, 'rgba(255, 105, 180, 0.4)');
        gradiente.addColorStop(1, 'rgba(255, 105, 180, 0)');
        let modo = 'montos';

        const grafica = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dias.etiquetas,
                datasets: [{
                    label: 'Ventas', data: dias.montos,
                    borderColor: '#FF69B4', backgroundColor: gradiente, borderWidth: 3, fill: true, tension: 0.4,
                    pointBackgroundColor: '#FF69B4', pointBorderColor: '#fff', pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#D81B60', padding: 10, cornerRadius: 8,
                        callbacks: {
                            label: function (c) {
                                return modo === 'montos' ? cordobas(c.parsed.y) : c.parsed.y + ' venta' + (c.parsed.y === 1 ? '' : 's');
                            },
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true, grid: { color: '#f3f4f6' }, border: { display: false },
                        ticks: {
                            precision: 0,
                            callback: function (v) { return modo === 'montos' ? 'C$ ' + Number(v).toLocaleString('en-US') : v; },
                        },
                    },
                    x: { grid: { display: false }, border: { display: false } },
                },
            },
        });

        const selector = document.querySelector('[data-grafica-modo]');
        if (selector) {
            selector.addEventListener('change', function () {
                modo = selector.value;
                grafica.data.datasets[0].data = dias[modo];
                grafica.update();
            });
        }
    }

    // 2. Productos más vendidos (unidades)
    const top = leer('datos-top-productos');
    const canvasDona = document.getElementById('doughnutChart');
    if (top && canvasDona && top.unidades.length) {
        new Chart(canvasDona.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: top.etiquetas,
                datasets: [{
                    data: top.unidades,
                    backgroundColor: ['#D81B60', '#FF69B4', '#C084FC', '#F9A8D4', '#FBCFE8', '#E5E7EB'],
                    borderWidth: 2, borderColor: '#ffffff', hoverOffset: 4,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '68%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, padding: 10, color: '#4b5563' },
                    },
                    tooltip: {
                        backgroundColor: '#D81B60', padding: 10, cornerRadius: 8,
                        callbacks: { label: function (c) { return ' ' + c.label + ': ' + c.parsed + ' u.'; } },
                    },
                },
            },
        });
    }
});
