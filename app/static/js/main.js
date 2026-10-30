/* Main Interactive JavaScript for Smart Library */

document.addEventListener('DOMContentLoaded', function() {
    // Auto dismiss bootstrap alert toasts after 5s
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Initialize all Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

function printElement(elementId) {
    const printContent = document.getElementById(elementId).outerHTML;
    const originalContent = document.body.innerHTML;
    document.body.innerHTML = `<html><head><title>Print</title><link rel="stylesheet" href="/static/css/custom.css"><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"></head><body style="display:flex;justify-content:center;align-items:center;height:100vh;">${printContent}</body></html>`;
    window.print();
    document.body.innerHTML = originalContent;
    window.location.reload();
}
