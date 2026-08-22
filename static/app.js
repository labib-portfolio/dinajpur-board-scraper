// Dinajpur Board Result Portal 2026 — Master Client Script
document.addEventListener('DOMContentLoaded', () => {
    
    // ==========================================
    // 1. Navigation Tab Switching
    // ==========================================
    const navTabBtns = document.querySelectorAll('.nav-tab-btn');
    const tabViews = document.querySelectorAll('.tab-view');

    navTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTabId = btn.getAttribute('data-tab');
            
            navTabBtns.forEach(b => b.classList.remove('active'));
            tabViews.forEach(v => v.classList.remove('active', 'hidden'));
            
            btn.classList.add('active');
            tabViews.forEach(v => {
                if (v.id === targetTabId) {
                    v.classList.add('active');
                } else {
                    v.classList.add('hidden');
                }
            });

            // Lazy load board summary on first visit to board tab
            if (targetTabId === 'tab-board' && !boardSummaryLoaded) {
                loadBoardSummary();
            }
        });
    });


    // ==========================================
    // 2. 🎓 Student Result Search (Home Screen)
    // ==========================================
    const studentSearchForm = document.getElementById('student-search-form');
    const studentRollInput = document.getElementById('student-roll-input');
    const studentSpinner = document.getElementById('student-spinner');
    const studentPlaceholder = document.getElementById('student-placeholder');
    const studentMarksheetCard = document.getElementById('student-marksheet-card');
    const studentErrorBox = document.getElementById('student-error-box');
    const studentErrorMsg = document.getElementById('student-error-msg');
    const btnPrintMarksheet = document.getElementById('btn-print-marksheet');

    // Quick Sample Chips
    document.querySelectorAll('.chip-btn').forEach(chip => {
        chip.addEventListener('click', () => {
            const roll = chip.getAttribute('data-roll');
            if (roll) {
                studentRollInput.value = roll;
                executeStudentSearch(roll);
            }
        });
    });

    if (studentSearchForm) {
        studentSearchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const roll = studentRollInput.value.trim();
            if (roll) {
                executeStudentSearch(roll);
            }
        });
    }

    if (btnPrintMarksheet) {
        btnPrintMarksheet.addEventListener('click', () => {
            window.print();
        });
    }

    async function executeStudentSearch(roll) {
        studentSpinner.classList.remove('hidden');
        studentPlaceholder.classList.add('hidden');
        studentMarksheetCard.classList.add('hidden');
        studentErrorBox.classList.add('hidden');

        try {
            const response = await fetch(`/api/student/${encodeURIComponent(roll)}`);
            const data = await response.json();

            if (data.success && data.data) {
                renderMarksheet(data.data, data.cached);
            } else {
                showStudentError(data.error || `Roll ${roll} could not be retrieved from the board.`);
            }
        } catch (err) {
            showStudentError(`Network error while fetching roll ${roll}: ${err.message}`);
        } finally {
            studentSpinner.classList.add('hidden');
        }
    }

    function renderMarksheet(record, isCached) {
        document.getElementById('ms-roll').textContent = record.roll_no || '--';
        document.getElementById('ms-name').textContent = record.student_name || '--';
        document.getElementById('ms-father').textContent = record.father_name || '--';
        document.getElementById('ms-mother').textContent = record.mother_name || '--';
        document.getElementById('ms-institute').textContent = record.institute || '--';
        document.getElementById('ms-group').textContent = record.group || 'GENERAL';
        document.getElementById('ms-total-marks').textContent = record.total_marks || 'N/A';

        // Result Status Badge
        const resVal = record.result || 'N/A';
        const isPass = resVal.includes('GPA');
        const badgeElem = document.getElementById('ms-result-badge');
        badgeElem.innerHTML = isPass 
            ? `<span class="badge-passed">PASSED (${resVal})</span>`
            : `<span class="badge-failed">FAILED (${resVal})</span>`;

        // Subject Grades
        const gradesTbody = document.getElementById('ms-grades-tbody');
        gradesTbody.innerHTML = '';

        const subjects = record.subject_grades || [];
        if (subjects.length > 0) {
            subjects.forEach(sub => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="bold">${sub.sub_code || '--'}</td>
                    <td>${sub.subject_name || '--'}</td>
                    <td class="grade-val">${sub.grade || '--'}</td>
                `;
                gradesTbody.appendChild(tr);
            });
        } else {
            gradesTbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Subject-wise breakdown not available for this record.</td></tr>`;
        }

        const sourceInfo = document.getElementById('ms-source-info');
        if (isCached) {
            sourceInfo.textContent = '⚡ Verified Record loaded instantly from Local District Cache';
        } else {
            sourceInfo.textContent = '🌐 Live Record synchronized directly with Dinajpur Board';
        }

        studentMarksheetCard.classList.remove('hidden');
    }

    function showStudentError(msg) {
        studentErrorMsg.textContent = msg;
        studentErrorBox.classList.remove('hidden');
    }


    // ==========================================
    // 3. 🏛️ District & Upazilla Explorer
    // ==========================================
    let boardSummaryLoaded = false;
    let boardData = null;
    let currentUpazillaRecords = [];
    let filteredRecords = [];
    let currentPage = 1;
    const pageSize = 50;

    const selectDistrict = document.getElementById('select-district');
    const selectUpazilla = document.getElementById('select-upazilla');
    const tableSearchInput = document.getElementById('table-search-input');
    const filterStatusSelect = document.getElementById('filter-status-select');
    const upazillaSummaryBar = document.getElementById('upazilla-summary-bar');
    const upazillaRosterTbody = document.getElementById('upazilla-roster-tbody');
    const tableRecordCount = document.getElementById('table-record-count');
    const paginationInfo = document.getElementById('pagination-info');
    const btnPrevPage = document.getElementById('btn-prev-page');
    const btnNextPage = document.getElementById('btn-next-page');
    const btnDownloadCsv = document.getElementById('btn-download-upazilla-csv');
    const btnDownloadJson = document.getElementById('btn-download-upazilla-json');

    async function loadBoardSummary() {
        try {
            const resp = await fetch('/api/board/summary');
            boardData = await resp.json();
            boardSummaryLoaded = true;

            // Populate Board KPI Cards
            document.getElementById('board-total-students').textContent = (boardData.total_students || 0).toLocaleString();
            document.getElementById('board-pass-rate').textContent = (boardData.pass_rate || 0) + '%';
            document.getElementById('board-passed-sub').textContent = `${(boardData.total_passed || 0).toLocaleString()} Passed (${boardData.pass_rate}%)`;
            document.getElementById('board-failed-count').textContent = (boardData.total_failed || 0).toLocaleString();
            document.getElementById('board-failed-sub').textContent = `${(boardData.total_failed || 0).toLocaleString()} Failed`;
            document.getElementById('board-gpa5-count').textContent = (boardData.total_gpa5 || 0).toLocaleString();

            // Populate District Dropdown
            selectDistrict.innerHTML = '<option value="">-- Choose District --</option>';
            const districts = Object.keys(boardData.districts || {});
            districts.forEach(dist => {
                const opt = document.createElement('option');
                opt.value = dist;
                opt.textContent = `${dist} (${boardData.districts[dist].total_records.toLocaleString()} Students)`;
                selectDistrict.appendChild(opt);
            });

            // Auto-select first district if available
            if (districts.length > 0) {
                selectDistrict.value = districts[0];
                handleDistrictChange(districts[0]);
            }
        } catch (err) {
            console.error('Failed to load board summary:', err);
        }
    }

    function handleDistrictChange(districtKey) {
        if (!districtKey || !boardData || !boardData.districts[districtKey]) {
            selectUpazilla.innerHTML = '<option value="">Select a district first</option>';
            selectUpazilla.disabled = true;
            return;
        }

        const districtInfo = boardData.districts[districtKey];
        selectUpazilla.innerHTML = '<option value="">-- Choose Upazilla --</option>';
        
        districtInfo.upazillas.forEach(upz => {
            const opt = document.createElement('option');
            opt.value = upz.slug;
            opt.textContent = `${upz.name} (${upz.total_records.toLocaleString()} Students - ${upz.pass_rate}% Pass)`;
            selectUpazilla.appendChild(opt);
        });

        selectUpazilla.disabled = false;

        // Auto-select first upazilla
        if (districtInfo.upazillas.length > 0) {
            selectUpazilla.value = districtInfo.upazillas[0].slug;
            loadUpazillaDetails(districtKey, districtInfo.upazillas[0].slug);
        }
    }

    selectDistrict.addEventListener('change', () => {
        handleDistrictChange(selectDistrict.value);
    });

    selectUpazilla.addEventListener('change', () => {
        if (selectDistrict.value && selectUpazilla.value) {
            loadUpazillaDetails(selectDistrict.value, selectUpazilla.value);
        }
    });

    async function loadUpazillaDetails(district, upazillaSlug) {
        upazillaRosterTbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted" style="padding: 40px;">Loading ${upazillaSlug.toUpperCase()} student records...</td></tr>`;

        try {
            const resp = await fetch(`/api/board/upazilla/${encodeURIComponent(district)}/${encodeURIComponent(upazillaSlug)}`);
            const data = await resp.json();

            currentUpazillaRecords = data.records || [];
            
            // Populate Summary Bar
            document.getElementById('sum-upazilla-name').textContent = data.upazila || upazillaSlug.toUpperCase();
            document.getElementById('sum-district-name').textContent = data.district || district;
            document.getElementById('sum-total-count').textContent = currentUpazillaRecords.length.toLocaleString();
            
            const passed = currentUpazillaRecords.filter(r => String(r.result).includes('GPA')).length;
            const failed = currentUpazillaRecords.length - passed;
            const gpa5 = currentUpazillaRecords.filter(r => String(r.result).includes('5.00')).length;
            const passRate = currentUpazillaRecords.length > 0 ? (100 * passed / currentUpazillaRecords.length).toFixed(1) : '0';

            document.getElementById('sum-passed-count').textContent = passed.toLocaleString();
            document.getElementById('sum-pass-rate').textContent = passRate + '%';
            document.getElementById('sum-failed-count').textContent = failed.toLocaleString();
            document.getElementById('sum-gpa5-count').textContent = gpa5.toLocaleString();
            document.getElementById('sum-schools-count').textContent = data.summary?.institutions_count || '--';

            upazillaSummaryBar.classList.remove('hidden');

            // Setup CSV & JSON Download Links
            btnDownloadCsv.onclick = () => {
                window.location.href = `/api/board/export/${encodeURIComponent(district)}/${encodeURIComponent(upazillaSlug)}/csv`;
            };
            btnDownloadJson.onclick = () => {
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `results_${district}_${upazillaSlug}.json`;
                a.click();
            };

            applyTableFilters();
        } catch (err) {
            upazillaRosterTbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger" style="padding: 40px;">Error loading upazilla: ${err.message}</td></tr>`;
        }
    }

    function applyTableFilters() {
        const query = (tableSearchInput.value || '').trim().toLowerCase();
        const statusFilter = filterStatusSelect.value;

        filteredRecords = currentUpazillaRecords.filter(r => {
            // Status filter
            const res = String(r.result || '');
            if (statusFilter === 'PASSED' && !res.includes('GPA')) return false;
            if (statusFilter === 'FAILED' && res.includes('GPA')) return false;
            if (statusFilter === 'GPA5' && !res.includes('5.00')) return false;

            // Search query filter
            if (query) {
                const rollMatch = String(r.roll_no || '').toLowerCase().includes(query);
                const nameMatch = String(r.student_name || '').toLowerCase().includes(query);
                const instMatch = String(r.institute || '').toLowerCase().includes(query);
                return rollMatch || nameMatch || instMatch;
            }
            return true;
        });

        currentPage = 1;
        renderTablePage();
    }

    tableSearchInput.addEventListener('input', applyTableFilters);
    filterStatusSelect.addEventListener('change', applyTableFilters);

    function renderTablePage() {
        tableRecordCount.textContent = filteredRecords.length.toLocaleString();
        
        const totalPages = Math.max(1, Math.ceil(filteredRecords.length / pageSize));
        currentPage = Math.min(Math.max(1, currentPage), totalPages);

        paginationInfo.textContent = `Page ${currentPage} of ${totalPages}`;
        btnPrevPage.disabled = (currentPage <= 1);
        btnNextPage.disabled = (currentPage >= totalPages);

        const startIdx = (currentPage - 1) * pageSize;
        const pageItems = filteredRecords.slice(startIdx, startIdx + pageSize);

        if (pageItems.length === 0) {
            upazillaRosterTbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted" style="padding: 40px;">No student records match your search criteria.</td></tr>`;
            return;
        }

        upazillaRosterTbody.innerHTML = '';
        pageItems.forEach((rec, idx) => {
            const isPass = String(rec.result || '').includes('GPA');
            const statusBadge = isPass 
                ? `<span class="badge-passed" style="font-size: 11px; padding: 2px 6px;">${rec.result}</span>`
                : `<span class="badge-failed" style="font-size: 11px; padding: 2px 6px;">${rec.result || 'FAILED'}</span>`;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="text-muted">${startIdx + idx + 1}</td>
                <td class="bold font-mono">${rec.roll_no}</td>
                <td class="bold">${rec.student_name || '--'}</td>
                <td class="text-muted">${rec.father_name || '--'}</td>
                <td>${rec.institute || '--'}</td>
                <td>${rec.group || 'GENERAL'}</td>
                <td>${statusBadge}</td>
                <td class="bold">${rec.total_marks || '--'}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline btn-view-ms" data-roll="${rec.roll_no}">📄 View</button>
                </td>
            `;
            
            tr.querySelector('.btn-view-ms').addEventListener('click', (e) => {
                e.stopPropagation();
                openMarksheetModal(rec);
            });

            tr.addEventListener('click', () => {
                openMarksheetModal(rec);
            });

            upazillaRosterTbody.appendChild(tr);
        });
    }

    btnPrevPage.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderTablePage();
        }
    });

    btnNextPage.addEventListener('click', () => {
        currentPage++;
        renderTablePage();
    });


    // ==========================================
    // 4. Marksheet Modal Popup
    // ==========================================
    const marksheetModal = document.getElementById('marksheet-modal');
    const modalMarksheetContent = document.getElementById('modal-marksheet-content');
    const btnCloseModal = document.getElementById('btn-close-modal');

    function openMarksheetModal(record) {
        const isPass = String(record.result || '').includes('GPA');
        const badge = isPass 
            ? `<span class="badge-passed">PASSED (${record.result})</span>`
            : `<span class="badge-failed">FAILED (${record.result})</span>`;

        let gradesHtml = '';
        if (record.subject_grades && record.subject_grades.length > 0) {
            gradesHtml = record.subject_grades.map(sub => `
                <tr>
                    <td class="bold">${sub.sub_code || '--'}</td>
                    <td>${sub.subject_name || '--'}</td>
                    <td class="grade-val">${sub.grade || '--'}</td>
                </tr>
            `).join('');
        } else {
            gradesHtml = `<tr><td colspan="3" class="text-center text-muted">Subject-wise grades not available.</td></tr>`;
        }

        modalMarksheetContent.innerHTML = `
            <div class="marksheet-header">
                <div class="board-emblem">🏛️</div>
                <div class="board-heading">
                    <h2>BOARD OF INTERMEDIATE AND SECONDARY EDUCATION, DINAJPUR</h2>
                    <h3>SECONDARY SCHOOL CERTIFICATE EXAMINATION, 2026</h3>
                    <div class="subheading">Official Academic Transcript & Marksheet</div>
                </div>
            </div>
            <div class="meta-table-wrapper">
                <table class="marksheet-meta-table">
                    <tbody>
                        <tr>
                            <td class="meta-label">Roll No</td>
                            <td class="meta-value bold">${record.roll_no}</td>
                            <td class="meta-label">Group</td>
                            <td class="meta-value">${record.group || 'GENERAL'}</td>
                        </tr>
                        <tr>
                            <td class="meta-label">Student Name</td>
                            <td class="meta-value bold primary">${record.student_name || '--'}</td>
                            <td class="meta-label">Type</td>
                            <td class="meta-value">REGULAR</td>
                        </tr>
                        <tr>
                            <td class="meta-label">Father's Name</td>
                            <td class="meta-value">${record.father_name || '--'}</td>
                            <td class="meta-label">Board</td>
                            <td class="meta-value">DINAJPUR</td>
                        </tr>
                        <tr>
                            <td class="meta-label">Mother's Name</td>
                            <td class="meta-value">${record.mother_name || '--'}</td>
                            <td class="meta-label">Upazilla / District</td>
                            <td class="meta-value">${record.upazila || '--'}, ${record.district || 'DINAJPUR'}</td>
                        </tr>
                        <tr>
                            <td class="meta-label">Institute</td>
                            <td class="meta-value" colspan="3">${record.institute || '--'}</td>
                        </tr>
                        <tr class="result-highlight-row">
                            <td class="meta-label">RESULT</td>
                            <td class="meta-value">${badge}</td>
                            <td class="meta-label">Total Marks</td>
                            <td class="meta-value bold">${record.total_marks || 'N/A'}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div class="grades-table-wrapper mt-3">
                <h4 class="grades-heading">Subject-Wise Grade Details:</h4>
                <table class="grades-table">
                    <thead>
                        <tr>
                            <th style="width: 100px;">Subject Code</th>
                            <th>Subject Name</th>
                            <th style="width: 120px; text-align: center;">Letter Grade</th>
                        </tr>
                    </thead>
                    <tbody>${gradesHtml}</tbody>
                </table>
            </div>
        `;

        marksheetModal.classList.remove('hidden');
    }

    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', () => {
            marksheetModal.classList.add('hidden');
        });
    }

    marksheetModal.addEventListener('click', (e) => {
        if (e.target === marksheetModal) {
            marksheetModal.classList.add('hidden');
        }
    });


    // ==========================================
    // 5. 📡 Live Monitor Stream
    // ==========================================
    let monitorInterval = null;
    const btnToggleMonitor = document.getElementById('btn-toggle-monitor-stream');

    async function syncMonitorData() {
        try {
            const resp = await fetch('/api/live-status');
            const data = await resp.json();

            const records = data.records || [];
            const summary = data.summary || {};
            const total = summary.total_rolls_in_file || records.length;
            const completed = records.length;
            const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

            document.getElementById('mon-stat-count').textContent = `${completed.toLocaleString()} / ${total.toLocaleString()}`;
            document.getElementById('mon-stat-percent').textContent = `${percent}% Completed`;
            document.getElementById('mon-stat-success').textContent = (summary.total_success || completed).toLocaleString();
            document.getElementById('mon-progress-percent-label').textContent = `${percent}%`;
            document.getElementById('mon-progress-bar-fill').style.width = `${percent}%`;
            document.getElementById('mon-stream-count').textContent = completed.toLocaleString();
            document.getElementById('mon-remaining-text').textContent = `${(total - completed).toLocaleString()} remaining`;

            if (records.length > 0) {
                const latest = records[records.length - 1];
                document.getElementById('mon-stat-latest-roll').textContent = latest.roll_no || '--';
                document.getElementById('mon-stat-latest-name').textContent = latest.student_name || '--';

                const streamTbody = document.getElementById('mon-stream-tbody');
                const last15 = records.slice(-15).reverse();
                streamTbody.innerHTML = last15.map((r, i) => `
                    <tr>
                        <td class="text-muted">${records.length - i}</td>
                        <td class="bold font-mono">${r.roll_no}</td>
                        <td class="bold">${r.student_name || '--'}</td>
                        <td class="text-muted">${r.father_name || '--'}</td>
                        <td>${r.institute || '--'}</td>
                        <td><span class="${String(r.result).includes('GPA') ? 'badge-passed' : 'badge-failed'}" style="font-size: 11px; padding: 2px 6px;">${r.result}</span></td>
                        <td class="bold">${r.total_marks || '--'}</td>
                    </tr>
                `).join('');
            }
        } catch (err) {
            console.error('Error syncing monitor:', err);
        }
    }

    if (btnToggleMonitor) {
        monitorInterval = setInterval(syncMonitorData, 2500);
        syncMonitorData();
    }


    // ==========================================
    // 6. ⚙️ Custom Scraper Tool Mode
    // ==========================================
    const modeSingle = document.getElementById('mode-single');
    const modeBatch = document.getElementById('mode-batch');
    const singleSection = document.getElementById('single-mode-section');
    const batchSection = document.getElementById('batch-mode-section');
    const btnProceed = document.getElementById('btn-proceed');
    const jsonOutput = document.getElementById('json-output');
    const btnCopyJson = document.getElementById('btn-copy-json');

    if (modeSingle && modeBatch) {
        modeSingle.addEventListener('click', () => {
            modeSingle.classList.add('active');
            modeBatch.classList.remove('active');
            singleSection.classList.remove('hidden');
            batchSection.classList.add('hidden');
        });
        modeBatch.addEventListener('click', () => {
            modeBatch.classList.add('active');
            modeSingle.classList.remove('active');
            batchSection.classList.remove('hidden');
            singleSection.classList.add('hidden');
        });
    }

    if (btnCopyJson) {
        btnCopyJson.addEventListener('click', () => {
            navigator.clipboard.writeText(jsonOutput.textContent);
            btnCopyJson.textContent = '✅ Copied!';
            setTimeout(() => { btnCopyJson.textContent = '📋 Copy JSON'; }, 2000);
        });
    }
});
