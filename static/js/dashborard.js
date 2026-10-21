document.addEventListener("DOMContentLoaded", function() {
    
    // 1. Gráfica de Línea (Ventas 7 días)
    const canvasLine = document.getElementById('lineChart');
    if (canvasLine) {
        const ctxLine = canvasLine.getContext('2d');
        
        let gradient = ctxLine.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(255, 105, 180, 0.4)'); 
        gradient.addColorStop(1, 'rgba(255, 105, 180, 0)');

        new Chart(ctxLine, {
            type: 'line',
            data: {
                labels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
                datasets: [{
                    label: 'Ventas (C$)',
                    data: [2000, 3500, 3200, 4500, 3500, 6000, 7000],
                    borderColor: '#FF69B4', 
                    backgroundColor: gradient,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#FF69B4',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false }, 
                    tooltip: { backgroundColor: '#D81B60', padding: 10, cornerRadius: 8 } 
                },
                scales: {
                    y: { beginAtZero: true, grid: { borderDash: [4, 4], color: '#f3f4f6' }, border: {display: false} },
                    x: { grid: { display: false }, border: {display: false} }
                }
            }
        });
    }

    // 2. Gráfica de Dona (Productos más vendidos)
    const canvasDoughnut = document.getElementById('doughnutChart');
    if (canvasDoughnut) {
        const ctxDoughnut = canvasDoughnut.getContext('2d');
        
        new Chart(ctxDoughnut, {
            type: 'doughnut',
            data: {
                labels: ['Labial Matte', 'Paleta de sombras', 'Skincare', 'Base de maquillaje', 'Otros'],
                datasets: [{
                    // Valores actualizados según el nuevo diseño
                    data: [22, 18, 15, 12, 23],
                    backgroundColor: ['#D81B60', '#FF69B4', '#C084FC', '#F9A8D4', '#FBCFE8'],
                    borderWidth: 2,
                    borderColor: '#ffffff',
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { usePointStyle: true, boxWidth: 10, font: { size: 11, family: 'sans-serif' }, padding: 15, color: '#4b5563' }
                    },
                    tooltip: { backgroundColor: '#D81B60', padding: 10, cornerRadius: 8 }
                }
            }
        });
    }
});