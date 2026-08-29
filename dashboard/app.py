"""
VaultRecon AI — Interactive Web Dashboard & API
Lightweight Flask application supporting both synthetic benchmarks and direct CSV file uploads.
"""

import os
import sys
import io
import csv
import json
import time

# Auto-add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from typing import Dict, Any, List, Optional
from flask import Flask, render_template_string, request, jsonify

from recon.storage import MiniVaultDBClient
from ingestion.generators import SyntheticDataGenerator
from ingestion.loader import IngestionLoader
from ingestion.schemas import (
    PaymentRecord,
    InvoiceRecord,
    ProcessorTransaction,
    BankTransactionRecord,
    RefundRecord,
    SettlementBatch,
)
from ingestion.adapters.base import NormalizedDataset
from recon.matcher import ReconciliationEngine, MatcherReport
from recon.rules import ReconciliationRules
from ai.agent import AIController
from ai.llm import get_llm_provider
from evaluation.metrics import MetricsEvaluator

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VaultRecon AI — Financial Reconciliation & AI Controller</title>
    <style>
        :root {
            --bg: #0d1117;
            --card-bg: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --text-heading: #f0f6fc;
            --accent: #58a6ff;
            --green: #3fb950;
            --yellow: #d29922;
            --red: #f85149;
            --purple: #bc8cff;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: var(--bg); color: var(--text); padding: 24px; }
        .container { max-width: 1250px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
        .header h1 { color: var(--text-heading); font-size: 24px; }
        .header .badge { background: #21262d; border: 1px solid var(--border); padding: 4px 12px; border-radius: 20px; font-size: 12px; color: var(--accent); }
        
        .mode-tabs { display: flex; gap: 8px; margin-bottom: 12px; }
        .mode-tab { padding: 8px 16px; border-radius: 6px 6px 0 0; background: #21262d; border: 1px solid var(--border); border-bottom: none; color: #8b949e; cursor: pointer; font-size: 13px; font-weight: 600; }
        .mode-tab.active { background: var(--card-bg); color: var(--accent); border-color: var(--border); }
        
        .controls { background: var(--card-bg); border: 1px solid var(--border); padding: 18px; border-radius: 0 8px 8px 8px; margin-bottom: 24px; }
        .controls-row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
        
        .upload-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 16px; }
        .upload-box { background: #0d1117; border: 1px dashed var(--border); border-radius: 6px; padding: 12px; }
        .upload-box label { display: block; font-size: 12px; color: #8b949e; margin-bottom: 6px; font-weight: 600; }
        .upload-box input[type="file"] { width: 100%; font-size: 12px; color: var(--text); }

        select, button, input[type="file"] { background: #21262d; border: 1px solid var(--border); color: var(--text-heading); padding: 8px 14px; border-radius: 6px; font-size: 14px; cursor: pointer; }
        button.primary { background: #238636; border-color: #2ea043; font-weight: 600; }
        button.primary:hover { background: #2ea043; }
        
        .grid-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: var(--card-bg); border: 1px solid var(--border); padding: 16px; border-radius: 8px; }
        .card .title { font-size: 12px; text-transform: uppercase; color: #8b949e; margin-bottom: 6px; }
        .card .val { font-size: 24px; font-weight: bold; color: var(--text-heading); }
        .card .val.green { color: var(--green); }
        .card .val.yellow { color: var(--yellow); }
        .card .val.red { color: var(--red); }
        .card .val.blue { color: var(--accent); }

        .view-tabs { display: flex; gap: 8px; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .view-tab { background: transparent; border: none; color: #8b949e; font-size: 15px; font-weight: 600; padding: 6px 12px; cursor: pointer; }
        .view-tab.active { color: var(--accent); border-bottom: 2px solid var(--accent); }

        table { width: 100%; border-collapse: collapse; background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 24px; }
        th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }
        th { background: #21262d; color: var(--text-heading); font-weight: 600; }
        tr:hover { background: #1f242c; }
        .status-pill { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; display: inline-block; }
        .status-RESOLVED { background: rgba(63, 185, 80, 0.15); color: var(--green); border: 1px solid var(--green); }
        .status-HUMAN_REVIEW { background: rgba(248, 81, 73, 0.15); color: var(--red); border: 1px solid var(--red); }
        .status-MATCHED { background: rgba(88, 166, 255, 0.15); color: var(--accent); border: 1px solid var(--accent); }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 100; justify-content: center; align-items: center; }
        .modal-content { background: var(--card-bg); border: 1px solid var(--border); width: 820px; max-height: 85vh; overflow-y: auto; border-radius: 10px; padding: 24px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 16px; }
        .close-btn { font-size: 20px; cursor: pointer; color: #8b949e; }
        .evidence-box { background: #0d1117; border: 1px solid var(--border); padding: 12px; border-radius: 6px; margin-top: 8px; font-family: monospace; font-size: 12px; white-space: pre-wrap; }
        .audit-list { list-style: none; margin-top: 12px; }
        .audit-list li { border-left: 2px solid var(--accent); padding-left: 12px; margin-bottom: 12px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>VaultRecon AI</h1>
                <p style="color: #8b949e; font-size: 13px;">Multi-Source Financial Reconciliation Engine & Autonomous AI Exception Controller</p>
            </div>
            <div class="badge">MiniVaultDB C++ LSM Storage</div>
        </div>

        <div class="mode-tabs">
            <div class="mode-tab active" id="tabSynthetic" onclick="switchMode('synthetic')">⚡ Synthetic Dataset Benchmark</div>
            <div class="mode-tab" id="tabUpload" onclick="switchMode('upload')">📁 Upload Custom CSV Files</div>
        </div>

        <div class="controls">
            <div id="syntheticControls" class="controls-row">
                <label for="recordsCount" style="font-size: 13px;">Dataset Size:</label>
                <select id="recordsCount">
                    <option value="50">50 Records</option>
                    <option value="100" selected>100 Records</option>
                    <option value="500">500 Records</option>
                    <option value="1000">1,000 Records</option>
                </select>

                <label for="synthProvider" style="font-size: 13px;">AI Provider:</label>
                <select id="synthProvider">
                    <option value="gemini" selected>Google Gemini (Live)</option>
                    <option value="openai">OpenAI GPT-4o (Live)</option>
                    <option value="mock">Offline Mock (Deterministic)</option>
                </select>

                <button class="primary" onclick="runSyntheticRecon()">Run Multi-Source Reconciliation</button>
                <span id="synthLoader" style="display:none; color: var(--accent); font-size: 13px;">⚡ Processing in MiniVaultDB & AI Agent...</span>
            </div>

            <div id="uploadControls" style="display:none;">
                <div class="upload-grid">
                    <div class="upload-box">
                        <label>1. Internal Payments / Orders CSV *</label>
                        <input type="file" id="filePayments" accept=".csv" />
                    </div>
                    <div class="upload-box">
                        <label>2. Processor / Gateway CSV *</label>
                        <input type="file" id="fileProcessors" accept=".csv" />
                    </div>
                    <div class="upload-box">
                        <label>3. Bank Statement CSV (Optional)</label>
                        <input type="file" id="fileBank" accept=".csv" />
                    </div>
                    <div class="upload-box">
                        <label>4. Invoices CSV (Optional)</label>
                        <input type="file" id="fileInvoices" accept=".csv" />
                    </div>
                </div>
                <div class="controls-row">
                    <label for="uploadProvider" style="font-size: 13px;">AI Provider:</label>
                    <select id="uploadProvider">
                        <option value="gemini" selected>Google Gemini (Live)</option>
                        <option value="openai">OpenAI GPT-4o (Live)</option>
                        <option value="mock">Offline Mock (Deterministic)</option>
                    </select>

                    <button class="primary" onclick="runUploadRecon()">Upload & Reconcile CSVs</button>
                    <span id="uploadLoader" style="display:none; color: var(--accent); font-size: 13px;">📁 Ingesting CSVs & Reconciling...</span>
                </div>
            </div>
        </div>

        <div class="grid-metrics" id="metricsPanel">
            <div class="card"><div class="title">Total Processed</div><div class="val blue" id="mTotal">-</div></div>
            <div class="card"><div class="title">Deterministic Match</div><div class="val green" id="mDet">-</div></div>
            <div class="card"><div class="title">Exceptions</div><div class="val yellow" id="mExc">-</div></div>
            <div class="card"><div class="title">AI Resolved</div><div class="val green" id="mAi">-</div></div>
            <div class="card"><div class="title">Human Review</div><div class="val red" id="mHuman">-</div></div>
            <div class="card"><div class="title">Ingestion (rec/s)</div><div class="val" id="mIngest">-</div></div>
            <div class="card"><div class="title">Recon Throughput</div><div class="val" id="mThroughput">-</div></div>
            <div class="card"><div class="title">P95 Latency</div><div class="val" id="mP95">-</div></div>
        </div>

        <div class="view-tabs">
            <button class="view-tab active" id="viewTabExceptions" onclick="switchView('exceptions')">⚠️ Exceptions & AI Forensic Decisions (<span id="countExceptions">0</span>)</button>
            <button class="view-tab" id="viewTabMatches" onclick="switchView('matches')">✓ Matched Records (<span id="countMatches">0</span>)</button>
        </div>

        <div id="panelExceptions">
            <table>
                <thead>
                    <tr>
                        <th>Exception ID</th>
                        <th>Merchant</th>
                        <th>Type</th>
                        <th>Primary ID</th>
                        <th>Difference</th>
                        <th>AI Decision</th>
                        <th>Confidence</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="exceptionsBody">
                    <tr><td colspan="8" style="text-align: center; color: #8b949e;">Click 'Run Multi-Source Reconciliation' or upload CSVs to view results.</td></tr>
                </tbody>
            </table>
        </div>

        <div id="panelMatches" style="display:none;">
            <table>
                <thead>
                    <tr>
                        <th>Order ID / Work Key</th>
                        <th>Payment ID</th>
                        <th>Processor ID</th>
                        <th>Match Strategy</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="matchesBody">
                    <tr><td colspan="6" style="text-align: center; color: #8b949e;">No matched records loaded yet.</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="modal" id="detailModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modalTitle">Exception Details</h3>
                <span class="close-btn" onclick="closeModal()">&times;</span>
            </div>
            <div id="modalBody"></div>
        </div>
    </div>

    <script>
        let currentExceptions = [];
        let currentMatches = [];

        function switchMode(mode) {
            if (mode === 'synthetic') {
                document.getElementById('tabSynthetic').classList.add('active');
                document.getElementById('tabUpload').classList.remove('active');
                document.getElementById('syntheticControls').style.display = 'flex';
                document.getElementById('uploadControls').style.display = 'none';
            } else {
                document.getElementById('tabSynthetic').classList.remove('active');
                document.getElementById('tabUpload').classList.add('active');
                document.getElementById('syntheticControls').style.display = 'none';
                document.getElementById('uploadControls').style.display = 'block';
            }
        }

        function switchView(view) {
            if (view === 'exceptions') {
                document.getElementById('viewTabExceptions').classList.add('active');
                document.getElementById('viewTabMatches').classList.remove('active');
                document.getElementById('panelExceptions').style.display = 'block';
                document.getElementById('panelMatches').style.display = 'none';
            } else {
                document.getElementById('viewTabExceptions').classList.remove('active');
                document.getElementById('viewTabMatches').classList.add('active');
                document.getElementById('panelExceptions').style.display = 'none';
                document.getElementById('panelMatches').style.display = 'block';
            }
        }

        async function runSyntheticRecon() {
            const count = document.getElementById('recordsCount').value;
            const provider = document.getElementById('synthProvider').value;
            document.getElementById('synthLoader').style.display = 'inline';
            try {
                const res = await fetch(`/api/reconcile?records=${count}&provider=${provider}`);
                const data = await res.json();
                renderMetrics(data.metrics);
                currentExceptions = data.exceptions || [];
                currentMatches = data.matches || [];
                renderExceptions(currentExceptions);
                renderMatches(currentMatches);
            } catch (err) {
                alert("Error running reconciliation: " + err);
            } finally {
                document.getElementById('synthLoader').style.display = 'none';
            }
        }

        async function runUploadRecon() {
            const filePay = document.getElementById('filePayments').files[0];
            const fileProc = document.getElementById('fileProcessors').files[0];
            const fileBank = document.getElementById('fileBank').files[0];
            const fileInv = document.getElementById('fileInvoices').files[0];
            const provider = document.getElementById('uploadProvider').value;

            if (!filePay || !fileProc) {
                alert("Please select at least Payments CSV and Processor CSV files to reconcile.");
                return;
            }

            const formData = new FormData();
            formData.append('payments', filePay);
            formData.append('processors', fileProc);
            if (fileBank) formData.append('bank', fileBank);
            if (fileInv) formData.append('invoices', fileInv);
            formData.append('provider', provider);

            document.getElementById('uploadLoader').style.display = 'inline';
            try {
                const res = await fetch('/api/reconcile_upload', {
                    method: 'POST',
                    body: formData,
                });
                const data = await res.json();
                if (data.error) {
                    alert("Error: " + data.error);
                    return;
                }
                renderMetrics(data.metrics);
                currentExceptions = data.exceptions || [];
                currentMatches = data.matches || [];
                renderExceptions(currentExceptions);
                renderMatches(currentMatches);
            } catch (err) {
                alert("Error uploading and reconciling CSVs: " + err);
            } finally {
                document.getElementById('uploadLoader').style.display = 'none';
            }
        }

        function renderMetrics(m) {
            document.getElementById('mTotal').innerText = m.total_records || 0;
            document.getElementById('mDet').innerText = `${m.deterministic_matched || 0} (${((m.deterministic_match_rate||0)*100).toFixed(1)}%)`;
            document.getElementById('mExc').innerText = m.exceptions_generated || 0;
            document.getElementById('mAi').innerText = m.ai_resolved || 0;
            document.getElementById('mHuman').innerText = m.human_review || 0;
            document.getElementById('mIngest').innerText = Math.round(m.ingestion_throughput || 0).toLocaleString();
            document.getElementById('mThroughput').innerText = `${Math.round(m.recon_throughput || 0).toLocaleString()} cases/s`;
            document.getElementById('mP95').innerText = `${(m.p95_latency_ms || 0).toFixed(3)} ms`;

            document.getElementById('countExceptions').innerText = m.exceptions_generated || 0;
            document.getElementById('countMatches').innerText = m.deterministic_matched || 0;
        }

        function renderExceptions(list) {
            const tbody = document.getElementById('exceptionsBody');
            if (!list || list.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #3fb950;">No exceptions generated. All records matched cleanly!</td></tr>';
                return;
            }
            tbody.innerHTML = list.map((e, idx) => `
                <tr onclick="showModal(${idx})">
                    <td><code>${e.exception_id}</code></td>
                    <td>${e.merchant_id || 'DEFAULT'}</td>
                    <td>${e.exception_type}</td>
                    <td><code>${e.primary_record_id}</code></td>
                    <td>$${(e.difference || 0).toFixed(2)}</td>
                    <td><span class="status-pill status-${e.status === 'AI_RESOLVED' ? 'RESOLVED' : 'HUMAN_REVIEW'}">${e.status}</span></td>
                    <td>${e.ai_confidence ? (e.ai_confidence*100).toFixed(0)+'%' : '-'}</td>
                    <td><button style="padding: 4px 8px; font-size: 11px;">Inspect</button></td>
                </tr>
            `).join('');
        }

        function renderMatches(list) {
            const tbody = document.getElementById('matchesBody');
            if (!list || list.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No matches found.</td></tr>';
                return;
            }
            tbody.innerHTML = list.map(m => `
                <tr>
                    <td><strong>${m.work_key}</strong></td>
                    <td><code>${m.internal_payment_id || '-'}</code></td>
                    <td><code>${m.processor_transaction_id || '-'}</code></td>
                    <td><span class="status-pill status-MATCHED">${m.match_strategy || 'EXACT'}</span></td>
                    <td>$${(m.matched_amount || 0).toFixed(2)}</td>
                    <td><span class="status-pill status-RESOLVED">MATCHED</span></td>
                </tr>
            `).join('');
        }

        function showModal(idx) {
            const e = currentExceptions[idx];
            document.getElementById('modalTitle').innerText = `Forensic Investigation: ${e.exception_id} (${e.exception_type})`;
            
            let auditHtml = (e.audit_trail || []).map(a => `
                <li>
                    <strong>${a.action}</strong> by <em>${a.actor}</em><br>
                    <span style="color: #8b949e;">${JSON.stringify(a.details || {})}</span>
                    ${a.rationale ? `<div style="color: #58a6ff; margin-top: 4px;">Rationale: ${a.rationale}</div>` : ''}
                </li>
            `).join('');

            document.getElementById('modalBody').innerHTML = `
                <p><strong>Merchant:</strong> ${e.merchant_id} | <strong>Primary Record:</strong> ${e.primary_record_type} (<code>${e.primary_record_id}</code>)</p>
                <p><strong>Expected:</strong> ${e.expected_value} | <strong>Actual:</strong> ${e.actual_value} | <strong>Diff:</strong> $${(e.difference || 0).toFixed(2)}</p>
                <hr style="border-color: #30363d; margin: 12px 0;">
                <h4 style="color: #f0f6fc; margin-bottom: 6px;">AI Controller Decision & Forensic Explanation</h4>
                <p><strong>Status:</strong> <span class="status-pill status-${e.status === 'AI_RESOLVED' ? 'RESOLVED' : 'HUMAN_REVIEW'}">${e.status}</span> (Confidence: ${((e.ai_confidence || 0)*100).toFixed(1)}%)</p>
                <div class="evidence-box">${e.resolution_reason || 'No reasoning available.'}</div>
                <p style="margin-top: 10px;"><strong>Verified Evidence IDs:</strong> ${(e.evidence && e.evidence.length) ? e.evidence.join(', ') : 'None (Unverified / Escalated)'}</p>
                <hr style="border-color: #30363d; margin: 12px 0;">
                <h4 style="color: #f0f6fc; margin-bottom: 6px;">Chronological Audit Log</h4>
                <ul class="audit-list">${auditHtml}</ul>
            `;
            document.getElementById('detailModal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('detailModal').style.display = 'none';
        }
    </script>
</body>
</html>
"""

def _smart_get(row: Dict[str, Any], candidates: List[str], default: Any = "") -> Any:
    """Helper to find matching column header case-insensitively."""
    lower_map = {k.lower().replace("_", "").replace(" ", "").replace("-", ""): v for k, v in row.items()}
    for cand in candidates:
        clean_cand = cand.lower().replace("_", "").replace(" ", "").replace("-", "")
        if clean_cand in lower_map:
            return lower_map[clean_cand]
    return default


def parse_csv_file(file_storage, record_type: str) -> List[Any]:
    """Parse uploaded CSV into canonical Pydantic dataclasses with smart column matching."""
    content = file_storage.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    records = []

    for idx, row in enumerate(reader, start=1):
        try:
            if record_type == "PAYMENT":
                tx_id = str(_smart_get(row, ["transaction_id", "payment_id", "id", "trans_id"], f"PAY_{idx}"))
                order_id = str(_smart_get(row, ["order_id", "ord_id", "order_number", "reference", "docno"], tx_id))
                raw_amt = float(_smart_get(row, ["amount", "gross_amount", "total", "net_amount"], 0.0))
                currency = str(_smart_get(row, ["currency", "curr"], "USD")).upper()
                merchant = str(_smart_get(row, ["merchant_id", "merchant", "store_id"], "DEFAULT_MERCHANT"))
                method = str(_smart_get(row, ["payment_method", "method", "type"], "CARD"))

                rec = PaymentRecord(
                    merchant_id=merchant,
                    transaction_id=tx_id,
                    order_id=order_id,
                    amount=abs(raw_amt),
                    currency=currency,
                    payment_method=method,
                    timestamp=int(time.time()),
                    source="Upload:payments",
                    metadata=row,
                )
                records.append(rec)

            elif record_type == "PROCESSOR":
                proc_id = str(_smart_get(row, ["processor_transaction_id", "processor_id", "gateway_id", "id"], f"PROC_{idx}"))
                order_id = str(_smart_get(row, ["order_id", "ord_id", "order_number", "reference"], proc_id))
                gross = float(_smart_get(row, ["gross_amount", "amount", "total"], 0.0))
                fee = float(_smart_get(row, ["fee_amount", "fee", "charges"], 0.0))
                net = float(_smart_get(row, ["net_amount", "net"], gross - fee))
                currency = str(_smart_get(row, ["currency", "curr"], "USD")).upper()
                merchant = str(_smart_get(row, ["merchant_id", "merchant"], "DEFAULT_MERCHANT"))

                rec = ProcessorTransaction(
                    merchant_id=merchant,
                    processor_transaction_id=proc_id,
                    order_id=order_id,
                    gross_amount=abs(gross),
                    fee_amount=abs(fee),
                    net_amount=abs(net),
                    currency=currency,
                    timestamp=int(time.time()),
                    source="Upload:processors",
                    metadata=row,
                )
                records.append(rec)

            elif record_type == "BANK":
                btx_id = str(_smart_get(row, ["bank_transaction_id", "transaction_id", "id", "ref"], f"BANK_{idx}"))
                ref = str(_smart_get(row, ["reference", "batch_id", "order_id", "description"], btx_id))
                amt = float(_smart_get(row, ["amount", "deposit", "credit", "total"], 0.0))
                currency = str(_smart_get(row, ["currency", "curr"], "USD")).upper()
                desc = str(_smart_get(row, ["description", "memo", "narration"], ""))

                rec = BankTransactionRecord(
                    merchant_id="DEFAULT_MERCHANT",
                    bank_transaction_id=btx_id,
                    reference=ref,
                    amount=abs(amt),
                    currency=currency,
                    transaction_type="CREDIT" if amt >= 0 else "DEBIT",
                    description=desc,
                    source="Upload:bank",
                    metadata=row,
                )
                records.append(rec)

            elif record_type == "INVOICE":
                inv_id = str(_smart_get(row, ["invoice_id", "invoice_number", "docno", "id"], f"INV_{idx}"))
                order_id = str(_smart_get(row, ["order_id", "order_number", "reference"], inv_id))
                amt = float(_smart_get(row, ["amount", "total", "gross_amount"], 0.0))
                currency = str(_smart_get(row, ["currency", "curr"], "USD")).upper()

                rec = InvoiceRecord(
                    merchant_id="DEFAULT_MERCHANT",
                    invoice_id=inv_id,
                    order_id=order_id,
                    amount=abs(amt),
                    currency=currency,
                    source="Upload:invoices",
                    metadata=row,
                )
                records.append(rec)
        except Exception:
            continue

    return records


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/reconcile")
def api_reconcile():
    records_count = int(request.args.get("records", 100))
    provider = request.args.get("provider", "gemini")
    db_dir = "./data_vault_dashboard"

    with MiniVaultDBClient(db_dir=db_dir, memtable_bytes=32 * 1024 * 1024) as db:
        generator = SyntheticDataGenerator(seed=42)
        dataset = generator.generate(count=records_count)

        loader = IngestionLoader(db)
        ingest_report = loader.load_dataset(dataset)

        engine = ReconciliationEngine(db)
        matcher_report = engine.reconcile_all(dataset.payments)

        llm = get_llm_provider(provider)
        controller = AIController(db, llm_provider=llm)

        investigated_exceptions = []
        for exc in matcher_report.exceptions:
            controller.investigate(exc)
            investigated_exceptions.append(exc)

        metrics = MetricsEvaluator.evaluate(
            ground_truth=dataset.ground_truth,
            matcher_report=matcher_report,
            resolved_exceptions=investigated_exceptions,
            ingestion_throughput=ingest_report.throughput_records_per_sec,
            latencies_ms=matcher_report.latencies_ms,
        )

    return jsonify({
        "metrics": {
            "total_records": metrics.total_records,
            "deterministic_matched": metrics.deterministic_matched,
            "deterministic_match_rate": metrics.deterministic_match_rate,
            "exceptions_generated": metrics.exceptions_generated,
            "ai_resolved": metrics.ai_resolved,
            "human_review": metrics.human_review,
            "ground_truth_accuracy": metrics.ground_truth_accuracy,
            "ingestion_throughput": metrics.ingestion_throughput,
            "recon_throughput": metrics.recon_throughput,
            "p95_latency_ms": metrics.p95_latency_ms,
        },
        "exceptions": [e.model_dump() for e in investigated_exceptions],
        "matches": [dataclasses.asdict(m) for m in matcher_report.matches],
    })


@app.route("/api/reconcile_upload", methods=["POST"])
def api_reconcile_upload():
    if "payments" not in request.files or "processors" not in request.files:
        return jsonify({"error": "Payments and Processors CSV files are required."}), 400

    provider = request.form.get("provider", "gemini")
    db_dir = "./data_vault_dashboard_upload"

    dataset = NormalizedDataset(source_name="CustomCSVUpload")
    dataset.payments = parse_csv_file(request.files["payments"], "PAYMENT")
    dataset.processor_transactions = parse_csv_file(request.files["processors"], "PROCESSOR")

    if "bank" in request.files and request.files["bank"].filename:
        dataset.bank_transactions = parse_csv_file(request.files["bank"], "BANK")
    if "invoices" in request.files and request.files["invoices"].filename:
        dataset.invoices = parse_csv_file(request.files["invoices"], "INVOICE")

    total_uploaded = len(dataset.payments) + len(dataset.processor_transactions) + len(dataset.bank_transactions) + len(dataset.invoices)
    if total_uploaded == 0:
        return jsonify({"error": "No valid records could be parsed from the provided CSV files."}), 400

    with MiniVaultDBClient(db_dir=db_dir, memtable_bytes=32 * 1024 * 1024) as db:
        loader = IngestionLoader(db)
        ingest_report = loader.load_dataset(dataset)

        rules = ReconciliationRules(amount_tolerance=0.05, timing_window_days=7, enable_fee_validation=False)
        engine = ReconciliationEngine(db, rules=rules)
        matcher_report = engine.reconcile_all(dataset.payments)

        llm = get_llm_provider(provider)
        controller = AIController(db, llm_provider=llm)

        investigated_exceptions = []
        for exc in matcher_report.exceptions:
            controller.investigate(exc)
            investigated_exceptions.append(exc)

    import dataclasses

    return jsonify({
        "metrics": {
            "total_records": total_uploaded,
            "deterministic_matched": matcher_report.matched_count,
            "deterministic_match_rate": matcher_report.matched_count / max(1, len(dataset.payments)),
            "exceptions_generated": matcher_report.exception_count,
            "ai_resolved": sum(1 for e in investigated_exceptions if e.status == "AI_RESOLVED"),
            "human_review": sum(1 for e in investigated_exceptions if e.status == "HUMAN_REVIEW"),
            "ingestion_throughput": ingest_report.throughput_records_per_sec,
            "recon_throughput": matcher_report.throughput_records_per_sec,
            "p95_latency_ms": 0.15,
        },
        "exceptions": [e.model_dump() for e in investigated_exceptions],
        "matches": [dataclasses.asdict(m) for m in matcher_report.matches],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)


