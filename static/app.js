document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements - Mode Switcher
    const modeSingleBtn = document.getElementById('mode-single');
    const modeBatchBtn = document.getElementById('mode-batch');
    const singleModeSection = document.getElementById('single-mode-section');
    const batchModeSection = document.getElementById('batch-mode-section');

    // DOM Elements - Form Config
    const targetUrlInput = document.getElementById('target-url');
    const inputsContainer = document.getElementById('inputs-container');
    const btnAddField = document.getElementById('btn-add-field');
    const btnLoadDemo = document.getElementById('btn-load-demo');
    const btnLoadDinajpur = document.getElementById('btn-load-dinajpur');
    const captchaInputName = document.getElementById('captcha-input-name');
    const captchaSelector = document.getElementById('captcha-selector');
    const buttonSelectorInput = document.getElementById('button-selector');
    const httpMethodSelect = document.getElementById('http-method');
    const formSelectorInput = document.getElementById('form-selector');
    const btnProceed = document.getElementById('btn-proceed');
    const spinner = document.getElementById('spinner');
    const btnProceedText = document.getElementById('btn-proceed-text');

    // DOM Elements - Batch Mode
    const rangeFieldName = document.getElementById('range-field-name');
    const rangeStart = document.getElementById('range-start');
    const rangeEnd = document.getElementById('range-end');
    const btnGenerateRange = document.getElementById('btn-generate-range');
    const batchTextList = document.getElementById('batch-text-list');
    const batchDelayInput = document.getElementById('batch-delay');
    const batchProgressContainer = document.getElementById('batch-progress-container');
    const batchStatusText = document.getElementById('batch-status-text');
    const batchCountText = document.getElementById('batch-count-text');
    const progressBarFill = document.getElementById('progress-bar-fill');

    // Quick Tester
    const testCaptchaText = document.getElementById('test-captcha-text');
    const btnTestCaptcha = document.getElementById('btn-test-captcha');
    const testCaptchaRes = document.getElementById('test-captcha-res');

    // Output Elements
    const jsonOutput = document.getElementById('json-output');
    const tablesOutput = document.getElementById('tables-output');
    const batchOutput = document.getElementById('batch-output');
    const contentOutput = document.getElementById('content-output');
    const logsOutput = document.getElementById('logs-output');
    const btnCopyJson = document.getElementById('btn-copy-json');
    const btnDownloadJson = document.getElementById('btn-download-json');
    const statusBar = document.getElementById('status-bar');
    const badgeStatus = document.getElementById('badge-status');
    const badgeCaptcha = document.getElementById('badge-captcha');
    const badgeTime = document.getElementById('badge-time');

    let currentMode = 'single'; // 'single' or 'batch'
    let currentJsonData = null;
    let batchRecordsAcc = [];

    // Mode Switcher Handler
    modeSingleBtn.addEventListener('click', () => {
        currentMode = 'single';
        modeSingleBtn.classList.add('active');
        modeBatchBtn.classList.remove('active');
        singleModeSection.classList.remove('hidden');
        batchModeSection.classList.add('hidden');
        btnProceedText.textContent = '🚀 Click Button & Scrape All Page Info';
    });

    modeBatchBtn.addEventListener('click', () => {
        currentMode = 'batch';
        modeBatchBtn.classList.add('active');
        modeSingleBtn.classList.remove('active');
        singleModeSection.classList.add('hidden');
        batchModeSection.classList.remove('hidden');
        btnProceedText.textContent = '🚀 Start Batch Scraping (List of Records)';
    });

    // Helper: Add Input Field Row (Single Mode)
    function addInputFieldRow(key = '', value = '') {
        const row = document.createElement('div');
        row.className = 'input-row';
        row.innerHTML = `
            <input type="text" class="field-key" placeholder="Field Name / ID" value="${key}">
            <input type="text" class="field-value" placeholder="Value to fill" value="${value}">
            <button type="button" class="btn-remove-row" title="Remove Field">✕</button>
        `;
        row.querySelector('.btn-remove-row').addEventListener('click', () => {
            row.remove();
        });
        inputsContainer.appendChild(row);
    }

    addInputFieldRow();

    btnAddField.addEventListener('click', () => {
        addInputFieldRow();
    });

    // Tab Switching
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const tabId = btn.getAttribute('data-tab');
            const el = document.getElementById(tabId);
            if (el) el.classList.add('active');
        });
    });

    // Range Generator
    btnGenerateRange.addEventListener('click', () => {
        const field = rangeFieldName.value.trim() || 'roll_no';
        const start = parseInt(rangeStart.value, 10);
        const end = parseInt(rangeEnd.value, 10);

        if (isNaN(start) || isNaN(end) || start > end) {
            alert('Please enter a valid start and end number (start <= end).');
            return;
        }

        if (end - start > 100) {
            if (!confirm(`You are generating ${end - start + 1} records. Continue?`)) return;
        }

        let lines = [`${field}`];
        for (let i = start; i <= end; i++) {
            lines.push(`${i}`);
        }
        batchTextList.value = lines.join('\n');
    });

    // DOM Elements - File Upload
    const batchFileInput = document.getElementById('batch-file-input');
    const fileUploadStatus = document.getElementById('file-upload-status');

    // File Upload Handler (.json, .csv, .txt)
    if (batchFileInput) {
        batchFileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (event) => {
                const content = event.target.result;
                try {
                    // Try parsing as JSON first
                    const parsed = JSON.parse(content);
                    let items = [];
                    if (Array.isArray(parsed)) {
                        items = parsed;
                    } else if (typeof parsed === 'object') {
                        // Check common wrapper keys: students, items, data, records, results
                        const key = Object.keys(parsed).find(k => Array.isArray(parsed[k]));
                        if (key) {
                            items = parsed[key];
                        } else {
                            items = [parsed];
                        }
                    }

                    batchTextList.value = JSON.stringify(items, null, 2);
                    fileUploadStatus.textContent = `✅ Successfully loaded ${items.length} records from "${file.name}"`;
                    fileUploadStatus.style.color = '#15803d';
                } catch (err) {
                    // Fallback to plain text / CSV
                    batchTextList.value = content;
                    const lines = content.split('\n').filter(l => l.trim().length > 0);
                    fileUploadStatus.textContent = `✅ Loaded ${lines.length} lines from "${file.name}"`;
                    fileUploadStatus.style.color = '#15803d';
                }
            };
            reader.readAsText(file);
        });
    }

    // Parse Textarea (Supports JSON Arrays, JSON Objects, or CSV/Text) into array of Dict items
    function parseBatchInputText(rawText) {
        const trimmed = rawText.trim();
        if (!trimmed) return [];

        // 1. Try parsing as direct JSON
        if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
            try {
                const parsed = JSON.parse(trimmed);
                if (Array.isArray(parsed)) {
                    return parsed.map(item => {
                        if (typeof item === 'object' && item !== null) return item;
                        return { roll_no: String(item) };
                    });
                } else if (typeof parsed === 'object') {
                    const key = Object.keys(parsed).find(k => Array.isArray(parsed[k]));
                    if (key) {
                        return parsed[key].map(item => {
                            if (typeof item === 'object' && item !== null) return item;
                            return { roll_no: String(item) };
                        });
                    }
                    return [parsed];
                }
            } catch (e) {
                // Not valid JSON, proceed to CSV/lines parser
            }
        }

        // 2. CSV / Tab / Space delimited parser
        const lines = trimmed.split('\n').map(l => l.trim()).filter(l => l.length > 0 && !l.startsWith('#'));
        if (lines.length === 0) return [];

        let headers = [];
        let dataStartIndex = 0;

        const firstLineParts = lines[0].split(/[,\t]/).map(p => p.trim());
        const isHeader = firstLineParts.some(p => isNaN(Number(p)));

        if (isHeader) {
            headers = firstLineParts;
            dataStartIndex = 1;
        } else {
            headers = ['roll_no', 'regi_no'];
        }

        const items = [];
        for (let i = dataStartIndex; i < lines.length; i++) {
            const parts = lines[i].split(/[,\t\s]+/).map(p => p.trim()).filter(p => p.length > 0);
            if (parts.length === 0) continue;

            const item = {};
            parts.forEach((val, idx) => {
                const key = headers[idx] || `field_${idx + 1}`;
                item[key] = val;
            });
            items.push(item);
        }
        return items;
    }

    // Load Presets
    btnLoadDemo.addEventListener('click', () => {
        const origin = window.location.origin;
        targetUrlInput.value = `${origin}/mock/`;
        inputsContainer.innerHTML = '';
        addInputFieldRow('roll_no', '108422');
        addInputFieldRow('registration_no', 'REG-2024-99');
        addInputFieldRow('exam_year', '2026');
        captchaInputName.value = 'captcha';
        captchaSelector.value = '#captcha-question';
        buttonSelectorInput.value = '#btn-proceed';
        formSelectorInput.value = '#result-form';
        httpMethodSelect.value = 'POST';

        // Also populate batch demo
        batchTextList.value = "roll_no, registration_no, exam_year\n108420, REG-2024-01, 2026\n108421, REG-2024-02, 2026\n108422, REG-2024-99, 2026";
    });

    btnLoadDinajpur.addEventListener('click', () => {
        targetUrlInput.value = 'https://results.dinajpurboard.gov.bd/search/student';
        inputsContainer.innerHTML = '';
        addInputFieldRow('roll_no', '108422');
        captchaInputName.value = 'captcha';
        captchaSelector.value = '';
        buttonSelectorInput.value = 'button[name="submit"]';
        formSelectorInput.value = '';
        httpMethodSelect.value = 'POST';

        batchTextList.value = "roll_no\n108420\n108421\n108422\n108423\n108424";
    });

    // Quick CAPTCHA Tester
    btnTestCaptcha.addEventListener('click', async () => {
        const text = testCaptchaText.value.trim();
        if (!text) return;
        testCaptchaRes.textContent = 'Solving...';
        try {
            const resp = await fetch('/api/test-captcha', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            const data = await resp.json();
            if (data.solution !== null) {
                testCaptchaRes.textContent = `✅ Result: ${data.solution}`;
                testCaptchaRes.style.color = 'var(--success)';
            } else {
                testCaptchaRes.textContent = '❌ Unrecognized format';
                testCaptchaRes.style.color = 'var(--danger)';
            }
        } catch (err) {
            testCaptchaRes.textContent = 'Error testing';
        }
    });

    // Main Proceed Button Handler
    btnProceed.addEventListener('click', () => {
        if (currentMode === 'single') {
            executeSingleScrape();
        } else {
            executeBatchScrape();
        }
    });

    // ================= SINGLE SCRAPE EXECUTION =================
    async function executeSingleScrape() {
        const targetUrl = targetUrlInput.value.trim();
        if (!targetUrl) {
            alert('Please enter a Target URL.');
            targetUrlInput.focus();
            return;
        }

        const inputFields = {};
        const rows = inputsContainer.querySelectorAll('.input-row');
        rows.forEach(row => {
            const k = row.querySelector('.field-key').value.trim();
            const v = row.querySelector('.field-value').value;
            if (k) inputFields[k] = v;
        });

        const payload = {
            url: targetUrl,
            input_fields: inputFields,
            captcha_input_name: captchaInputName.value.trim() || null,
            captcha_selector: captchaSelector.value.trim() || null,
            button_selector: buttonSelectorInput.value.trim() || null,
            form_selector: formSelectorInput.value.trim() || null,
            method: httpMethodSelect.value === 'AUTO' ? null : httpMethodSelect.value
        };

        btnProceed.disabled = true;
        spinner.classList.remove('hidden');
        btnProceedText.textContent = 'Clicking Button & Scraping...';
        statusBar.classList.add('hidden');
        batchProgressContainer.classList.add('hidden');
        btnCopyJson.disabled = true;
        btnDownloadJson.disabled = true;

        jsonOutput.textContent = 'Filling inputs, solving CAPTCHA, clicking button and scraping...';
        logsOutput.innerHTML = '<div class="log-entry">🚀 Starting single scrape engine...</div>';

        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            currentJsonData = result;
            renderSingleResults(result);
        } catch (err) {
            jsonOutput.textContent = JSON.stringify({ error: err.message }, null, 2);
            logsOutput.innerHTML += `<div class="log-entry" style="color: #f87171;">❌ Network Error: ${err.message}</div>`;
        } finally {
            btnProceed.disabled = false;
            spinner.classList.add('hidden');
            btnProceedText.textContent = '🚀 Click Button & Scrape All Page Info';
        }
    }

    // ================= BATCH SCRAPE EXECUTION =================
    async function executeBatchScrape() {
        const targetUrl = targetUrlInput.value.trim();
        if (!targetUrl) {
            alert('Please enter a Target URL.');
            targetUrlInput.focus();
            return;
        }

        const items = parseBatchInputText(batchTextList.value);
        if (items.length === 0) {
            alert('Please provide at least one record in the Batch Record List box.');
            batchTextList.focus();
            return;
        }

        const delay = parseFloat(batchDelayInput.value) || 1.0;

        const payload = {
            url: targetUrl,
            items: items,
            captcha_input_name: captchaInputName.value.trim() || null,
            captcha_selector: captchaSelector.value.trim() || null,
            button_selector: buttonSelectorInput.value.trim() || null,
            form_selector: formSelectorInput.value.trim() || null,
            method: httpMethodSelect.value === 'AUTO' ? null : httpMethodSelect.value,
            delay_seconds: delay
        };

        // Reset UI
        btnProceed.disabled = true;
        spinner.classList.remove('hidden');
        btnProceedText.textContent = `Batch Scraping (0/${items.length})...`;
        statusBar.classList.add('hidden');
        batchProgressContainer.classList.remove('hidden');
        progressBarFill.style.width = '0%';
        batchStatusText.textContent = `Starting batch scrape of ${items.length} records...`;
        batchCountText.textContent = `0 / ${items.length}`;

        batchRecordsAcc = [];
        initBatchTableView(items);

        // Switch to Batch tab automatically
        document.getElementById('tab-btn-batch').click();

        logsOutput.innerHTML = `<div class="log-entry">🚀 Initializing Batch Scraper for ${items.length} records...</div>`;

        try {
            const response = await fetch('/api/batch-scrape-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // keep remainder

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const eventData = JSON.parse(line.substring(6));
                        handleBatchEvent(eventData, items.length);
                    }
                }
            }

            // Final summary update
            const finalBatchData = {
                batch_summary: {
                    total_requested: items.length,
                    total_success: batchRecordsAcc.filter(r => r.success).length,
                    total_failed: batchRecordsAcc.filter(r => !r.success).length,
                    records: batchRecordsAcc
                }
            };
            currentJsonData = finalBatchData;
            jsonOutput.textContent = JSON.stringify(finalBatchData, null, 2);
            btnCopyJson.disabled = false;
            btnDownloadJson.disabled = false;

        } catch (err) {
            logsOutput.innerHTML += `<div class="log-entry" style="color: #f87171;">❌ Batch Error: ${err.message}</div>`;
        } finally {
            btnProceed.disabled = false;
            spinner.classList.add('hidden');
            btnProceedText.textContent = '🚀 Start Batch Scraping (List of Records)';
        }
    }

    function handleBatchEvent(event, totalItems) {
        if (event.type === 'start') {
            batchStatusText.textContent = `Batch started for ${event.total} records...`;
        } else if (event.type === 'item') {
            const idx = event.index;
            const rec = event.record;
            batchRecordsAcc.push(rec);

            // Update Progress Bar
            const percent = event.progress_percent || Math.round((idx / totalItems) * 100);
            progressBarFill.style.width = `${percent}%`;
            batchCountText.textContent = `${idx} / ${totalItems}`;
            batchStatusText.textContent = `Scraped item #${idx}: ${JSON.stringify(rec.item_inputs)} (${rec.success ? '✅ Success' : '❌ ' + (rec.error || 'Failed')})`;

            // Update Live Table Row
            updateBatchTableRow(idx, rec);

            // Append to Logs
            logsOutput.innerHTML += `<div class="log-entry">› [${idx}/${totalItems}] Inputs: ${JSON.stringify(rec.item_inputs)} ➔ Status: ${rec.status_code || 'Err'} (CAPTCHA: ${rec.captcha_info?.solution || 'N/A'})</div>`;
            logsOutput.scrollTop = logsOutput.scrollHeight;

        } else if (event.type === 'complete') {
            const s = event.summary;
            progressBarFill.style.width = '100%';
            batchStatusText.textContent = `🎉 Batch Complete! Success: ${s.total_success}, Failed: ${s.total_failed} (${s.total_elapsed_seconds}s)`;
            logsOutput.innerHTML += `<div class="log-entry" style="color: #4ade80;">🎉 Finished all ${s.total_requested} records in ${s.total_elapsed_seconds}s!</div>`;
        }
    }

    function initBatchTableView(items) {
        let html = '<table class="extracted-table">';
        html += '<thead><tr><th>#</th><th>Input Parameters</th><th>Status</th><th>CAPTCHA Answer</th><th>Extracted Summary / GPA</th></tr></thead>';
        html += '<tbody>';
        items.forEach((item, idx) => {
            html += `<tr id="batch-row-${idx + 1}">
                <td>${idx + 1}</td>
                <td><code>${escapeHtml(JSON.stringify(item))}</code></td>
                <td><span class="badge badge-neutral">Pending...</span></td>
                <td>-</td>
                <td>-</td>
            </tr>`;
        });
        html += '</tbody></table>';
        batchOutput.innerHTML = html;
    }

    function updateBatchTableRow(idx, rec) {
        const row = document.getElementById(`batch-row-${idx}`);
        if (!row) return;

        const statusBadge = rec.success
            ? `<span class="badge">✅ 200 OK</span>`
            : `<span class="badge badge-danger">❌ ${escapeHtml(rec.error || 'Failed')}</span>`;

        const captchaVal = rec.captcha_info?.solution !== null && rec.captcha_info?.solution !== undefined
            ? `<b>${rec.captcha_info.solution}</b> (${rec.captcha_info.question || ''})`
            : 'None';

        // Extract student name or GPA or table rows
        let summaryText = 'No data';
        const name = rec.student_name || rec.data?.key_value_data?.['Student Name'] || rec.data?.key_value_data?.['Name of Student'] || '';
        const gpa = rec.result || rec.data?.key_value_data?.['Result'] || '';
        const inst = rec.institute || rec.data?.key_value_data?.['Name of Institute'] || '';
        
        if (name || gpa) {
            summaryText = `<b>${escapeHtml(name)}</b> ${gpa ? `• <span style="color:#16a34a; font-weight:bold;">${escapeHtml(gpa)}</span>` : ''} ${inst ? `<br><small style="color:#64748b;">${escapeHtml(inst)}</small>` : ''}`;
        } else if (rec.full_data?.tables && rec.full_data.tables.length > 0) {
            summaryText = `${rec.full_data.tables[0].row_count} table rows extracted`;
        } else {
            summaryText = rec.full_data?.title || 'Page scraped';
        }

        row.innerHTML = `
            <td>${idx}</td>
            <td><code>${escapeHtml(rec.roll_no || JSON.stringify(rec.item_inputs))}</code></td>
            <td>${statusBadge}</td>
            <td>${captchaVal}</td>
            <td>${summaryText}</td>
        `;
    }

    // Render Single Results
    function renderSingleResults(result) {
        jsonOutput.textContent = JSON.stringify(result, null, 2);
        btnCopyJson.disabled = false;
        btnDownloadJson.disabled = false;

        statusBar.classList.remove('hidden');
        if (result.success) {
            badgeStatus.className = 'badge';
            badgeStatus.textContent = `✅ Success (${result.status_code || 200})`;
        } else {
            badgeStatus.className = 'badge badge-danger';
            badgeStatus.textContent = `❌ ${result.error || 'Failed'}`;
        }

        const captcha = result.captcha_info;
        if (captcha && captcha.solution !== null) {
            badgeCaptcha.className = 'badge badge-info';
            badgeCaptcha.textContent = `🧮 Solved: "${captcha.question || ''}" ➔ ${captcha.solution}`;
        } else {
            badgeCaptcha.className = 'badge badge-neutral';
            badgeCaptcha.textContent = 'CAPTCHA: None / Bypassed';
        }

        badgeTime.textContent = `⏱️ ${result.elapsed_seconds || 0}s`;

        if (result.logs && result.logs.length > 0) {
            logsOutput.innerHTML = result.logs.map(log => `<div class="log-entry">› ${escapeHtml(log)}</div>`).join('');
        }

        renderTablesView(result);
        renderContentView(result);
    }

    function renderTablesView(result) {
        const tables = result.data?.tables || [];
        if (tables.length === 0) {
            tablesOutput.innerHTML = '<p class="placeholder-text">No tabular data found in scraped response.</p>';
            return;
        }

        let html = '';
        tables.forEach(t => {
            html += `<h3 style="margin-top: 12px; margin-bottom: 8px;">Table #${t.table_index} (${t.row_count} rows)</h3>`;
            html += '<table class="extracted-table">';
            if (t.headers && t.headers.length > 0) {
                html += '<thead><tr>' + t.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('') + '</tr></thead>';
            }
            html += '<tbody>';
            t.rows.forEach(r => {
                html += '<tr>';
                Object.values(r).forEach(val => {
                    html += `<td>${escapeHtml(String(val))}</td>`;
                });
                html += '</tr>';
            });
            html += '</tbody></table>';
        });
        tablesOutput.innerHTML = html;
    }

    function renderContentView(result) {
        const data = result.data || {};
        let html = '';

        const kv = data.key_value_data || {};
        if (Object.keys(kv).length > 0) {
            html += '<h3 style="margin-bottom: 10px;">📋 Key Information</h3>';
            html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-bottom: 20px;">';
            for (const [k, v] of Object.entries(kv)) {
                html += `<div style="background: #f1f5f9; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0;">
                    <div style="font-size: 11px; color: #64748b; font-weight: bold; text-transform: uppercase;">${escapeHtml(k)}</div>
                    <div style="font-size: 14px; font-weight: 600; color: #0f172a; margin-top: 4px;">${escapeHtml(String(v))}</div>
                </div>`;
            }
            html += '</div>';
        }

        const sections = data.sections || [];
        if (sections.length > 0) {
            html += '<h3 style="margin-bottom: 10px;">📑 Headings & Content</h3>';
            sections.forEach(sec => {
                html += `<div style="margin-bottom: 12px; padding: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 6px;">
                    <strong style="color: #2563eb;">${escapeHtml(sec.heading)}</strong>
                    ${sec.content.length > 0 ? `<p style="font-size: 13px; color: #334155; margin-top: 4px;">${escapeHtml(sec.content.join(' '))}</p>` : ''}
                </div>`;
            });
        }

        const textSummary = data.full_text_summary || [];
        if (textSummary.length > 0) {
            html += '<h3 style="margin-top: 16px; margin-bottom: 8px;">📝 Page Text Preview</h3>';
            html += `<div style="max-height: 200px; overflow-y: auto; background: #f8fafc; padding: 12px; border-radius: 6px; font-size: 12px; color: #475569; border: 1px solid #e2e8f0;">`;
            html += textSummary.slice(0, 30).map(line => `<div>${escapeHtml(line)}</div>`).join('');
            html += '</div>';
        }

        if (!html) {
            html = '<p class="placeholder-text">No structured sections or key-value data found.</p>';
        }

        contentOutput.innerHTML = html;
    }

    // ================= LIVE PROGRESS MONITOR =================
    const btnLiveMonitor = document.getElementById('btn-live-monitor');
    let liveMonitorTimer = null;

    if (btnLiveMonitor) {
        btnLiveMonitor.addEventListener('click', toggleLiveMonitor);
    }

    function toggleLiveMonitor() {
        if (liveMonitorTimer) {
            clearInterval(liveMonitorTimer);
            liveMonitorTimer = null;
            btnLiveMonitor.textContent = '📡 Live Progress Monitor';
            btnLiveMonitor.style.background = '#16a34a';
            logsOutput.innerHTML += '<div class="log-entry" style="color: #f59e0b;">⏸️ Live Progress Monitor Paused.</div>';
            return;
        }

        // Activate Tab & Progress Bar
        const batchTabBtn = document.getElementById('tab-btn-batch');
        if (batchTabBtn) batchTabBtn.click();

        batchProgressContainer.classList.remove('hidden');
        btnLiveMonitor.textContent = '🔴 Monitoring Live (Click to Pause)';
        btnLiveMonitor.style.background = '#dc2626';

        // Poll immediately and set interval
        pollLiveProgress();
        liveMonitorTimer = setInterval(pollLiveProgress, 1800);
    }

    async function pollLiveProgress() {
        try {
            const resp = await fetch('/api/live-status');
            if (!resp.ok) return;
            const data = await resp.json();

            const summary = data.summary || {};
            const records = data.records || [];
            const total = summary.total_rolls_in_file || 3112;
            const scraped = records.length;
            const percent = Math.min(100, Math.round((scraped / total) * 100));

            // Update Progress Bar
            progressBarFill.style.width = `${percent}%`;
            batchCountText.textContent = `${scraped} / ${total} (${percent}%)`;
            batchStatusText.textContent = `🚀 Live Scraping Active • Success: ${summary.total_success || 0} • Failed: ${summary.total_failed || 0}`;

            // Update JSON Output & Buttons
            currentJsonData = data;
            jsonOutput.textContent = JSON.stringify(data, null, 2);
            btnCopyJson.disabled = false;
            btnDownloadJson.disabled = false;

            // Render Live Table
            renderLiveProgressTable(records);

        } catch (err) {
            console.error('Error polling live progress:', err);
        }
    }

    function renderLiveProgressTable(records) {
        if (!records || records.length === 0) {
            batchOutput.innerHTML = '<p class="placeholder-text">Waiting for scraped records to stream in...</p>';
            return;
        }

        let html = '<div style="margin-bottom: 8px; font-weight: bold; color: #1e293b; font-size: 13px;">📋 Live Scraped Students (' + records.length + ' records):</div>';
        html += '<div style="max-height: 480px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px;">';
        html += '<table class="extracted-table" style="margin: 0;">';
        html += '<thead style="position: sticky; top: 0; background: #f8fafc; z-index: 2;">';
        html += '<tr><th>#</th><th>Roll No</th><th>Student Name</th><th>Father\'s Name</th><th>Result / GPA</th><th>Institute</th><th>Status</th></tr>';
        html += '</thead><tbody>';

        // Render from newest to oldest for live streaming experience
        for (let i = records.length - 1; i >= 0; i--) {
            const r = records[i];
            const isSucc = r.success;
            const statusBadge = isSucc 
                ? '<span class="badge">✅ 200 OK</span>' 
                : '<span class="badge badge-danger">❌ Failed</span>';

            const gpaVal = r.result || '-';
            const gpaStyle = gpaVal.includes('GPA') ? 'color: #16a34a; font-weight: bold;' : (gpaVal.includes('FAILED') ? 'color: #dc2626; font-weight: bold;' : '');

            html += `<tr>
                <td><b>${r.index || (i + 1)}</b></td>
                <td><code>${escapeHtml(r.roll_no)}</code></td>
                <td><b>${escapeHtml(r.student_name || 'N/A')}</b></td>
                <td>${escapeHtml(r.father_name || '-')}</td>
                <td><span style="${gpaStyle}">${escapeHtml(gpaVal)}</span></td>
                <td><small style="color: #64748b;">${escapeHtml(r.institute || '-')}</small></td>
                <td>${statusBadge}</td>
            </tr>`;
        }

        html += '</tbody></table></div>';
        batchOutput.innerHTML = html;
    }

    // Auto-start live monitor if file exists
    setTimeout(pollLiveProgress, 1000);
});

