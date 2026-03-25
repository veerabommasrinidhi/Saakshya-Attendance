/* ============================================
   Smart Classroom Attendance System
   Main JavaScript with Chart.js Integration
   ============================================ */

// Global variables
let currentChart = null;
let attendanceChart = null;
let trendChart = null;
let socket = null;

// Initialize Socket.IO connection
function initSocket() {
    if (typeof io !== 'undefined') {
        socket = io();
        
        socket.on('connect', () => {
            console.log('Connected to WebSocket server');
        });
        
        socket.on('attendance_marked', (data) => {
            console.log('Attendance marked:', data);
            showNotification(`Attendance marked for ${data.student_name}`, 'success');
            refreshDashboard();
        });
        
        socket.on('new_student_registered', (data) => {
            console.log('New student registered:', data);
            showNotification(`New student ${data.name} registered`, 'info');
            refreshDashboard();
        });
        
        socket.on('attendance_update', (data) => {
            console.log('Attendance update:', data);
            refreshDashboard();
        });
    }
}

// Chart.js Configuration
const chartConfigs = {
    // Default options for all charts
    defaults: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                labels: {
                    color: '#ffffff',
                    font: {
                        family: 'Inter',
                        size: 12
                    }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: '#ffffff',
                bodyColor: '#a0a0a0',
                borderColor: '#667eea',
                borderWidth: 1,
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== undefined) {
                            label += context.parsed.y;
                        }
                        if (context.parsed !== undefined) {
                            label += context.parsed;
                        }
                        return label;
                    }
                }
            }
        }
    },
    
    // Donut/Pie chart options
    donut: {
        cutout: '60%',
        plugins: {
            legend: {
                position: 'bottom'
            }
        }
    },
    
    // Bar chart options
    bar: {
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: '#a0a0a0'
                }
            },
            x: {
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: '#a0a0a0'
                }
            }
        }
    },
    
    // Line chart options
    line: {
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: '#a0a0a0'
                }
            },
            x: {
                grid: {
                    color: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: {
                    color: '#a0a0a0'
                }
            }
        },
        elements: {
            line: {
                tension: 0.4
            }
        }
    }
};

// Create Donut Chart
function createDonutChart(canvasId, data, labels, colors) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    if (currentChart) {
        currentChart.destroy();
    }
    
    currentChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            ...chartConfigs.defaults,
            ...chartConfigs.donut,
            cutout: '60%'
        }
    });
    
    return currentChart;
}

// Create Bar Chart
function createBarChart(canvasId, data, labels, label, colors) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    if (attendanceChart) {
        attendanceChart.destroy();
    }
    
    attendanceChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: colors || 'rgba(102, 126, 234, 0.6)',
                borderColor: '#667eea',
                borderWidth: 1,
                borderRadius: 8,
                barPercentage: 0.7,
                categoryPercentage: 0.8
            }]
        },
        options: {
            ...chartConfigs.defaults,
            ...chartConfigs.bar,
            plugins: {
                ...chartConfigs.defaults.plugins,
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${label}: ${context.parsed.y}%`;
                        }
                    }
                }
            }
        }
    });
    
    return attendanceChart;
}

// Create Line Chart (Trend)
function createLineChart(canvasId, data, labels, label) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    if (trendChart) {
        trendChart.destroy();
    }
    
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                pointBackgroundColor: '#667eea',
                pointBorderColor: '#ffffff',
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            ...chartConfigs.defaults,
            ...chartConfigs.line,
            plugins: {
                ...chartConfigs.defaults.plugins,
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${label}: ${context.parsed.y}%`;
                        }
                    }
                }
            }
        }
    });
    
    return trendChart;
}

// Create Horizontal Bar Chart
function createHorizontalBarChart(canvasId, data, labels, label) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    if (trendChart) {
        trendChart.destroy();
    }
    
    trendChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: 'rgba(102, 126, 234, 0.6)',
                borderColor: '#667eea',
                borderWidth: 1,
                borderRadius: 8
            }]
        },
        options: {
            ...chartConfigs.defaults,
            indexAxis: 'y',
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#a0a0a0',
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#a0a0a0'
                    }
                }
            }
        }
    });
    
    return trendChart;
}

// Update Chart Data
function updateChartData(chart, newData, newLabels = null) {
    if (chart) {
        chart.data.datasets[0].data = newData;
        if (newLabels) {
            chart.data.labels = newLabels;
        }
        chart.update();
    }
}

// Create Attendance Overview Chart
function createAttendanceOverviewChart(present, absent, total) {
    const ctx = document.getElementById('attendanceOverviewChart');
    if (!ctx) return;
    
    const attendanceRate = (present / total * 100).toFixed(1);
    
    return createDonutChart(
        'attendanceOverviewChart',
        [present, absent],
        [`Present (${present})`, `Absent (${absent})`],
        ['#10b981', '#ef4444']
    );
}

// Create Student Performance Chart
function createStudentPerformanceChart(students) {
    const ctx = document.getElementById('studentPerformanceChart');
    if (!ctx) return;
    
    const names = students.slice(0, 10).map(s => s.name);
    const percentages = students.slice(0, 10).map(s => s.percentage);
    
    return createHorizontalBarChart(
        'studentPerformanceChart',
        percentages,
        names,
        'Attendance Percentage'
    );
}

// Create Weekly Trend Chart
function createWeeklyTrendChart(weeklyData) {
    const ctx = document.getElementById('weeklyTrendChart');
    if (!ctx) return;
    
    const days = weeklyData.map(d => d.date);
    const percentages = weeklyData.map(d => (d.present / d.total * 100).toFixed(1));
    
    return createLineChart(
        'weeklyTrendChart',
        percentages,
        days,
        'Attendance Rate (%)'
    );
}

// Create Monthly Breakdown Chart
function createMonthlyBreakdownChart(monthlyData) {
    const ctx = document.getElementById('monthlyBreakdownChart');
    if (!ctx) return;
    
    const months = monthlyData.map(m => m.month);
    const percentages = monthlyData.map(m => (m.present / m.total * 100).toFixed(1));
    
    return createBarChart(
        'monthlyBreakdownChart',
        percentages,
        months,
        'Attendance Rate (%)',
        'rgba(102, 126, 234, 0.6)'
    );
}

// Create Department Distribution Chart
function createDepartmentChart(departments) {
    const ctx = document.getElementById('departmentChart');
    if (!ctx) return;
    
    const deptNames = departments.map(d => d.name);
    const counts = departments.map(d => d.count);
    
    return createDonutChart(
        'departmentChart',
        counts,
        deptNames,
        ['#667eea', '#764ba2', '#10b981', '#f59e0b', '#ef4444', '#3b82f6']
    );
}

// Utility Functions
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} animate-fade-in-up`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    notification.style.maxWidth = '400px';
    notification.style.boxShadow = '0 10px 25px rgba(0,0,0,0.2)';
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <span>${message}</span>
            <button type="button" class="btn-close ms-auto" style="background: transparent; border: none; color: inherit; font-size: 20px; cursor: pointer;" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

// Format date
function formatDate(date) {
    const d = new Date(date);
    return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Format time
function formatTime(time) {
    const t = new Date(`2000-01-01T${time}`);
    return t.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Format number with percentage
function formatPercentage(value) {
    return `${value.toFixed(1)}%`;
}

// Debounce function for performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle function for performance
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Local storage helper
const storage = {
    set: (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            return false;
        }
    },
    get: (key, defaultValue = null) => {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            return defaultValue;
        }
    },
    remove: (key) => {
        localStorage.removeItem(key);
    },
    clear: () => {
        localStorage.clear();
    }
};

// API helper
const api = {
    async get(endpoint) {
        try {
            const response = await fetch(endpoint);
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            showNotification('Network error. Please try again.', 'error');
            return null;
        }
    },
    
    async post(endpoint, data) {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            showNotification('Network error. Please try again.', 'error');
            return null;
        }
    },
    
    async formPost(endpoint, formData) {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            showNotification('Network error. Please try again.', 'error');
            return null;
        }
    }
};

// Export functions for use in templates
window.createDonutChart = createDonutChart;
window.createBarChart = createBarChart;
window.createLineChart = createLineChart;
window.createHorizontalBarChart = createHorizontalBarChart;
window.createAttendanceOverviewChart = createAttendanceOverviewChart;
window.createStudentPerformanceChart = createStudentPerformanceChart;
window.createWeeklyTrendChart = createWeeklyTrendChart;
window.createMonthlyBreakdownChart = createMonthlyBreakdownChart;
window.createDepartmentChart = createDepartmentChart;
window.updateChartData = updateChartData;
window.showNotification = showNotification;
window.formatDate = formatDate;
window.formatTime = formatTime;
window.formatPercentage = formatPercentage;
window.storage = storage;
window.api = api;
window.initSocket = initSocket;

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
    console.log('Chart.js and utilities initialized');
});