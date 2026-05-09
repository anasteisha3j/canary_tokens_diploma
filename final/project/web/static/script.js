// CanaryTrap - JavaScript функціонал

// Оновлення даних в реальному часі
function refreshData() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            console.log('Дані оновлено:', data);
        })
        .catch(error => console.error('Помилка:', error));
}

// Періодичне оновлення (кожні 30 секунд)
setInterval(refreshData, 30000);

// Копіювання токена в буфер
function copyToken(tokenValue) {
    navigator.clipboard.writeText(tokenValue).then(() => {
        alert('Токен скопійовано!');
    });
}

// Підтвердження дій
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Фільтрація таблиці
function filterTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const filter = input.value.toLowerCase();
    const table = document.getElementById(tableId);
    const rows = table.getElementsByTagName('tr');

    for (let i = 1; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        let found = false;
        
        for (let j = 0; j < cells.length; j++) {
            const cell = cells[j];
            if (cell) {
                const text = cell.textContent || cell.innerText;
                if (text.toLowerCase().indexOf(filter) > -1) {
                    found = true;
                    break;
                }
            }
        }
        
        rows[i].style.display = found ? '' : 'none';
    }
}

// Експорт в CSV
function exportToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tr');
    const csv = [];
    
    for (const row of rows) {
        const cells = row.querySelectorAll('td, th');
        const rowData = [];
        for (const cell of cells) {
            rowData.push('"' + cell.innerText.replace(/"/g, '""') + '"');
        }
        csv.push(rowData.join(','));
    }
    
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
}

// Графіки (якщо використовуються Chart.js)
function initCharts() {
    // Тут можна додати ініціалізацію графіків
    console.log('Графіки ініціалізовано');
}

// Запуск при завантаженні сторінки
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
});