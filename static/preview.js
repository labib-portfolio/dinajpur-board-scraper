document.addEventListener('DOMContentLoaded', () => {
    let allRecords = [];
    let isStreaming = true;
    let pollTimer = null;

    // Elements
    const statProgressCount = document.getElementById('stat-progress-count');
    const statPercent = document.getElementById('stat-percent');
    const statSuccessCount = document.getElementById('stat-success-count');
    const statLatestRoll = document.getElementById('stat-latest-roll');
    const statLatestName = document.getElementById('stat-latest-name');
    const statSyncTime = document.getElementById('stat-sync-time');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const progressPercentageLabel = document.getElementById('progress-percentage-label');
    const progressRemainingText = document.getElementById('progress-remaining-text');
    const tableCount = document.getElementById('table-count');
    const liveTableBody = document.getElementById('live-table-body');
    const searchInput = document.getElementById('search-input');
    const filterResult = document.getElementById('filter-result');
    const btnToggleStream = document.getElementById('btn-toggle-stream');
    const btnExportCsv = document.getElementById('btn-export-csv');
    const btnExportJson = document.getElementById('btn-export-json');

    // Modal
    const modalDetails = document.getElementById('modal-details');
    const modalClose = document.getElementById('modal-close');
    const modalStudentTitle = document.getElementById('modal-student-title');
    const modalStudentBody = document.getElementById('modal-student-body');

    modalClose.addEventListener('click', () => modalDetails.classList.add('hidden'));
    modalDetails.addEventListener('click', (e) => {
        if (e.target === modalDetails) modalDetails.classList.add('hidden');
    });

    // Toggle Stream
    btnToggleStream.addEventListener('click', () => {
        isStreaming = !isStreaming;
        if (isStreaming) {
            btnToggleStream.textContent = '🔴 Live (Syncing)';
            btnToggleStream.className = 'btn btn-primary btn-sm';
            fetchLiveStatus();
            pollTimer = setInterval(fetchLiveStatus, 1500);
        } else {
            btnToggleStream.textContent = '⏸️ Paused';
            btnToggleStream.className = 'btn btn-secondary btn-sm';
            clearInterval(pollTimer);
        }
    });

    // Search and filter listeners
    searchInput.addEventListener('input', renderTable);
    filterResult.addEventListener('change', renderTable);

    // Initial fetch and start polling
    fetchLiveStatus();
    pollTimer = setInterval(fetchLiveStatus, 1500);

    async function fetchLiveStatus() {
        try {
            const res = await fetch('/api/live-status');
            if (!res.ok) return;
            const data = await res.json();

            const summary = data.summary || {};
            allRecords = data.records || [];

            const total = summary.total_rolls_in_file || 3112;
            const completed = allRecords.length;
            const percent = Math.min(100, ((completed / total) * 100)).toFixed(1);
            const remaining = Math.max(0, total - completed);

            // Update Stats
            statProgressCount.textContent = `${completed.toLocaleString()} / ${total.toLocaleString()}`;
            statPercent.textContent = `${percent}% Completed`;
            statSuccessCount.textContent = (summary.total_success || completed).toLocaleString();
            progressBarFill.style.width = `${percent}%`;
            progressPercentageLabel.textContent = `${percent}%`;
            progressRemainingText.textContent = `${remaining.toLocaleString()} rolls remaining`;
            statSyncTime.textContent = new Date().toLocaleTimeString();

            if (allRecords.length > 0) {
                const latest = allRecords[allRecords.length - 1];
                statLatestRoll.textContent = latest.roll_no || '--';
                statLatestName.textContent = `${latest.student_name || 'N/A'} (${latest.result || 'N/A'})`;
            }

            renderTable();
        } catch (err) {
            console.error('Error syncing live status:', err);
        }
    }

    function renderTable() {
        const query = searchInput.value.toLowerCase().trim();
        const filter = filterResult.value;

        let filtered = allRecords.filter(r => {
            if (filter === 'GPA' && !String(r.result || '').includes('GPA')) return false;
            if (filter === 'FAILED' && !String(r.result || '').includes('FAILED')) return false;

            if (query) {
                const rollMatch = String(r.roll_no || '').toLowerCase().includes(query);
                const nameMatch = String(r.student_name || '').toLowerCase().includes(query);
                const fatherMatch = String(r.father_name || '').toLowerCase().includes(query);
                const instMatch = String(r.institute || '').toLowerCase().includes(query);
                const gpaMatch = String(r.result || '').toLowerCase().includes(query);
                return rollMatch || nameMatch || fatherMatch || instMatch || gpaMatch;
            }
            return true;
        });

        tableCount.textContent = filtered.length.toLocaleString();

        if (filtered.length === 0) {
            liveTableBody.innerHTML = `<tr><td colspan="9" class="empty-state">No matching records found.</td></tr>`;
            return;
        }

        // Render from newest to oldest for live streaming experience
        let html = '';
        const displayList = [...filtered].reverse().slice(0, 300); // Display top 300 for blazing speed

        displayList.forEach((r, idx) => {
            const isSucc = r.success;
            const statusBadge = isSucc 
                ? '<span class="badge badge-success">200 OK</span>' 
                : '<span class="badge badge-danger">FAILED</span>';

            const gpaVal = r.result || '-';
            const gpaClass = gpaVal.includes('GPA') ? 'gpa-tag' : (gpaVal.includes('FAILED') ? 'fail-tag' : '');
            const marksVal = r.total_marks || '-';

            const subs = r.subject_grades || [];
            const subButton = subs.length > 0 
                ? `<button class="btn-view-subs" onclick="showStudentDetails('${r.roll_no}')">🔍 ${subs.length} Subjects</button>` 
                : '<span style="color: #6b7280;">-</span>';

            html += `<tr>
                <td style="color: #9ca3af; font-family: 'Fira Code', monospace;">${r.index || (filtered.length - idx)}</td>
                <td><strong style="font-family: 'Fira Code', monospace; color: #60a5fa;">${escapeHtml(r.roll_no)}</strong></td>
                <td><strong style="color: #ffffff;">${escapeHtml(r.student_name || 'N/A')}</strong></td>
                <td style="color: #9ca3af;">${escapeHtml(r.father_name || '-')}</td>
                <td><span class="${gpaClass}">${escapeHtml(gpaVal)}</span></td>
                <td style="font-family: 'Fira Code', monospace; color: #fbbf24;">${escapeHtml(marksVal)}</td>
                <td style="max-width: 260px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(r.institute || '')}">
                    ${escapeHtml(r.institute || '-')}
                </td>
                <td>${subButton}</td>
                <td>${statusBadge}</td>
            </tr>`;
        });

        liveTableBody.innerHTML = html;
    }

    // Window global for modal details
    window.showStudentDetails = function(rollNo) {
        const student = allRecords.find(r => String(r.roll_no) === String(rollNo));
        if (!student) return;

        modalStudentTitle.textContent = `Roll ${student.roll_no} — ${student.student_name || 'Student Details'}`;
        
        let html = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; font-size: 13px;">
                <div><span style="color: #9ca3af;">Father's Name:</span> <strong>${escapeHtml(student.father_name || '-')}</strong></div>
                <div><span style="color: #9ca3af;">Mother's Name:</span> <strong>${escapeHtml(student.mother_name || '-')}</strong></div>
                <div><span style="color: #9ca3af;">Institute:</span> <strong>${escapeHtml(student.institute || '-')}</strong></div>
                <div><span style="color: #9ca3af;">Result:</span> <strong style="color: #34d399;">${escapeHtml(student.result || '-')}</strong></div>
                <div><span style="color: #9ca3af;">Total Marks:</span> <strong style="color: #fbbf24;">${escapeHtml(student.total_marks || '-')}</strong></div>
                <div><span style="color: #9ca3af;">Group:</span> <strong>${escapeHtml(student.group || '-')}</strong></div>
            </div>
            <h4 style="margin-bottom: 8px; font-size: 13px; color: #60a5fa;">Subject-Wise Grades:</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid #374151; color: #9ca3af;">
                        <th style="padding: 6px;">Code</th>
                        <th style="padding: 6px;">Subject Name</th>
                        <th style="padding: 6px;">Grade</th>
                    </tr>
                </thead>
                <tbody>
        `;

        (student.subject_grades || []).forEach(sub => {
            html += `
                <tr style="border-bottom: 1px solid #1f2937;">
                    <td style="padding: 6px; font-family: monospace; color: #9ca3af;">${escapeHtml(sub.sub_code || '-')}</td>
                    <td style="padding: 6px;">${escapeHtml(sub.subject_name || '-')}</td>
                    <td style="padding: 6px; font-weight: bold; color: #34d399;">${escapeHtml(sub.grade || '-')}</td>
                </tr>
            `;
        });

        html += `</tbody></table>`;
        modalStudentBody.innerHTML = html;
        modalDetails.classList.remove('hidden');
    };

    // Export to JSON
    btnExportJson.addEventListener('click', () => {
        if (allRecords.length === 0) return;
        const blob = new Blob([JSON.stringify({ summary: { total: allRecords.length }, records: allRecords }, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dinajpur_board_scraped_results_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // Export to CSV
    btnExportCsv.addEventListener('click', () => {
        if (allRecords.length === 0) return;
        let csv = 'Index,Roll No,Student Name,Father Name,Mother Name,Institute,Group,Result,Total Marks\n';
        allRecords.forEach(r => {
            const row = [
                r.index || '',
                `"${r.roll_no || ''}"`,
                `"${(r.student_name || '').replace(/"/g, '""')}"`,
                `"${(r.father_name || '').replace(/"/g, '""')}"`,
                `"${(r.mother_name || '').replace(/"/g, '""')}"`,
                `"${(r.institute || '').replace(/"/g, '""')}"`,
                `"${r.group || ''}"`,
                `"${r.result || ''}"`,
                `"${r.total_marks || ''}"`
            ];
            csv += row.join(',') + '\n';
        });

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dinajpur_board_students_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
